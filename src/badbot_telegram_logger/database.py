"""
Database operations for Telegram message and action logging.

This module provides a comprehensive interface for interacting with the Supabase database,
handling message storage, action logging, and checkpoint management with proper error handling
and retry logic.
"""

import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union, Tuple, Callable
from contextlib import asynccontextmanager
from functools import lru_cache
import json

from telegram import Message, Chat, User, Update
from supabase import create_client, Client
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

try:
    from loguru import logger
except ImportError:
    # Fallback logging if loguru not available
    import logging
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)

from .config import Config
from .models import (
    MessageModel, ActionModel, CheckpointModel, 
    ChatInfoModel, UserInfoModel, ActionType, MessageType, ChatType
)


class DatabaseError(Exception):
    """Custom exception for database operations."""
    pass


class RetryableError(DatabaseError):
    """Exception for errors that should trigger a retry."""
    pass


class NonRetryableError(DatabaseError):
    """Exception for errors that should not trigger a retry."""
    pass


class ConnectionError(DatabaseError):
    """Exception for connection-related errors."""
    pass


class SupabaseManager:
    """
    Manages all interactions with the Supabase database.
    
    Provides methods for storing messages, actions, checkpoints, and managing
    chat/user information with proper error handling and retry logic.
    """
    
    def __init__(self, config: Config) -> None:
        """
        Initialize the Supabase manager.
        
        Args:
            config: Configuration object containing Supabase credentials
        """
        self.config = config
        self.client: Optional[Client] = None
        self.table_names = config.get_database_table_names()
        self._connection_lock = asyncio.Lock()
        self._initialized = False
        self._stats_cache: Dict[str, Any] = {}
        self._cache_ttl = 300  # 5 minutes cache TTL
        self._last_cache_update = datetime.now(timezone.utc)
        
    async def initialize(self) -> None:
        """Initialize the Supabase client and verify connection."""
        async with self._connection_lock:
            if self._initialized and self.client is not None:
                return
                
            try:
                self.client = create_client(
                    self.config.supabase_url,
                    self.config.supabase_key
                )
                
                # Test connection by attempting to read from a table
                await self._test_connection()
                self._initialized = True
                logger.info("Successfully connected to Supabase database")
                
            except Exception as e:
                logger.error(f"Failed to initialize Supabase client: {e}")
                raise ConnectionError(f"Database initialization failed: {e}") from e
    
    def _ensure_client(self) -> Client:
        """Ensure client is initialized and return it."""
        if not self.client:
            raise ConnectionError("Database client not initialized. Call initialize() first.")
        return self.client
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(RetryableError)
    )
    async def _test_connection(self) -> None:
        """Test the database connection."""
        try:
            client = self._ensure_client()
            
            # Try to query the checkpoints table (should exist)
            result = client.table(self.table_names["checkpoints"]).select("*").limit(1).execute()
            logger.debug("Database connection test successful")
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            # Determine if error is retryable
            if "connection" in str(e).lower() or "timeout" in str(e).lower():
                raise RetryableError(f"Connection test failed: {e}") from e
            else:
                raise NonRetryableError(f"Connection test failed: {e}") from e
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(RetryableError)
    )
    async def _execute_with_retry(
        self, 
        operation: Callable[..., Any], 
        operation_name: str,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute a database operation with retry logic.
        
        Args:
            operation: The database operation to execute
            operation_name: Name of the operation for logging
            *args: Arguments to pass to the operation
            **kwargs: Keyword arguments to pass to the operation
            
        Returns:
            The result of the operation
            
        Raises:
            DatabaseError: If the operation fails after all retries
        """
        try:
            if not self.client:
                await self.initialize()
                
            client = self._ensure_client()
            logger.debug(f"Executing {operation_name}")
            result = operation(client, *args, **kwargs)
            
            if hasattr(result, 'execute'):
                result = result.execute()
                
            logger.debug(f"Successfully executed {operation_name}. Result: {result.data}")
            return result
            
        except Exception as e:
            logger.warning(f"{operation_name} failed: {e}")
            
            # Determine if this is a retryable error
            error_str = str(e).lower()
            if any(keyword in error_str for keyword in ["connection", "timeout", "network", "503", "502", "500"]):
                raise RetryableError(f"Retryable error in {operation_name}: {e}") from e
            else:
                raise NonRetryableError(f"Non-retryable error in {operation_name}: {e}") from e
    
    async def store_message(self, message: Message, is_backfilled: bool = False) -> bool:
        """
        Store a Telegram message in the database.
        
        Args:
            message: The Telegram message to store
            is_backfilled: Whether this message is from backfill operation
            
        Returns:
            True if successful, False otherwise
        """
        try:
            message_model = self._convert_telegram_message(message, is_backfilled)
            message_dict = self._message_model_to_dict(message_model)
            
            def operation(client: Client) -> Any:
                return client.table(self.table_names["messages"]).upsert(
                    message_dict,
                    on_conflict="message_id,chat_id"
                )
            
            await self._execute_with_retry(
                operation, 
                f"store_message_{message.message_id}"
            )
            
            logger.debug(f"Stored message {message.message_id} from {message.from_user}")
            return True
            
        except NonRetryableError as e:
            logger.error(f"Non-retryable error storing message {message.message_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to store message {message.message_id}: {e}")
            return False
    
    async def store_messages_batch(
        self, 
        messages: List[Message], 
        is_backfilled: bool = False
    ) -> int:
        """
        Store multiple messages in a single batch operation.
        
        Args:
            messages: List of Telegram messages to store
            is_backfilled: Whether these messages are from backfill operation
            
        Returns:
            Number of successfully stored messages
        """
        if not messages:
            return 0
        
        try:
            message_dicts = []
            for msg in messages:
                try:
                    model = self._convert_telegram_message(msg, is_backfilled)
                    message_dict = self._message_model_to_dict(model)
                    message_dicts.append(message_dict)
                except Exception as e:
                    logger.warning(f"Failed to convert message {msg.message_id}: {e}")
                    continue
            
            if not message_dicts:
                return 0
            
            def operation(client: Client) -> Any:
                return client.table(self.table_names["messages"]).upsert(
                    message_dicts,
                    on_conflict="message_id,chat_id"
                )
            
            await self._execute_with_retry(
                operation,
                f"store_messages_batch_{len(message_dicts)}"
            )
            
            logger.info(f"Stored batch of {len(message_dicts)} messages")
            return len(message_dicts)
            
        except Exception as e:
            logger.error(f"Failed to store message batch: {e}")
            return 0
    
    async def store_action(
        self, 
        action_type: ActionType, 
        chat_id: Optional[int] = None,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        target_id: Optional[int] = None,
        target_type: Optional[str] = None,
        target_name: Optional[str] = None,
        action_data: Optional[Dict[str, Any]] = None,
        before_data: Optional[Dict[str, Any]] = None,
        after_data: Optional[Dict[str, Any]] = None,
        is_backfilled: bool = False
    ) -> bool:
        """
        Store a Telegram action/event in the database.
        
        Args:
            action_type: Type of action being logged
            chat_id: Chat ID where action occurred
            user_id: User ID who performed the action
            username: Username of action performer
            first_name: First name of action performer
            last_name: Last name of action performer
            target_id: ID of the target object
            target_type: Type of target object
            target_name: Name of target object
            action_data: Additional action data
            before_data: State before the action
            after_data: State after the action
            is_backfilled: Whether this action is from backfill operation
            
        Returns:
            True if successful, False otherwise
        """
        try:
            action_model = ActionModel(
                action_id=str(uuid.uuid4()),
                action_type=action_type,
                chat_id=chat_id,
                user_id=user_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                target_id=target_id,
                target_type=target_type,
                target_name=target_name,
                action_data=action_data or {},
                before_data=before_data,
                after_data=after_data,
                occurred_at=datetime.now(timezone.utc),
                is_backfilled=is_backfilled
            )
            
            action_dict = self._action_model_to_dict(action_model)
            
            def operation(client: Client) -> Any:
                return client.table(self.table_names["actions"]).insert(
                    action_dict
                )
            
            await self._execute_with_retry(
                operation,
                f"store_action_{action_type.value}"
            )
            
            logger.debug(f"Stored action {action_type.value} for chat {chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store action {action_type.value}: {e}")
            return False
    
    async def get_checkpoint(
        self, 
        checkpoint_type: str, 
        chat_id: Optional[int] = None
    ) -> Optional[CheckpointModel]:
        """
        Retrieve a checkpoint from the database.
        
        Args:
            checkpoint_type: Type of checkpoint to retrieve
            chat_id: Chat ID for the checkpoint
            
        Returns:
            CheckpointModel if found, None otherwise
        """
        try:
            def operation(client: Client) -> Any:
                query = client.table(self.table_names["checkpoints"]).select("*")
                
                # Build query conditions
                query = query.eq("checkpoint_type", checkpoint_type)
                
                if chat_id is not None:
                    query = query.eq("chat_id", chat_id)
                else:
                    query = query.is_("chat_id", "null")
                
                return query.limit(1)
            
            result = await self._execute_with_retry(
                operation,
                f"get_checkpoint_{checkpoint_type}"
            )
            
            if result.data:
                # Remove the 'id' field from the database result as it's not part of our model
                checkpoint_data = result.data[0].copy()
                checkpoint_data.pop('id', None)  # Remove the database-generated id field
                return CheckpointModel(**checkpoint_data)
            return None
            
        except Exception as e:
            logger.error(f"Failed to retrieve checkpoint {checkpoint_type}: {e}")
            return None
    
    async def update_checkpoint(
        self,
        checkpoint_type: str,
        last_processed_id: Optional[str] = None,
        last_processed_timestamp: Optional[datetime] = None,
        chat_id: Optional[int] = None,
        total_processed: Optional[int] = None,
        backfill_in_progress: Optional[bool] = None
    ) -> bool:
        """
        Update or create a checkpoint in the database.
        
        Args:
            checkpoint_type: Type of checkpoint
            last_processed_id: ID of last processed item
            last_processed_timestamp: Timestamp of last processed item
            chat_id: Chat ID for the checkpoint
            total_processed: Total number of items processed
            backfill_in_progress: Whether backfill is in progress
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Generate checkpoint ID
            checkpoint_id = f"{checkpoint_type}_{chat_id or 'global'}"
            
            # Check if checkpoint exists
            existing = await self.get_checkpoint(checkpoint_type, chat_id)
            
            if existing:
                # Update existing checkpoint
                update_data: Dict[str, Union[str, int, bool]] = {
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
                
                if last_processed_id is not None:
                    update_data["last_processed_id"] = last_processed_id
                if last_processed_timestamp is not None:
                    update_data["last_processed_timestamp"] = last_processed_timestamp.isoformat()
                if total_processed is not None:
                    update_data["total_processed"] = total_processed
                if backfill_in_progress is not None:
                    update_data["backfill_in_progress"] = backfill_in_progress
                
                def operation(client: Client) -> Any:
                    query = client.table(self.table_names["checkpoints"]).update(update_data)
                    return query.eq("checkpoint_id", existing.checkpoint_id)
                
            else:
                # Create new checkpoint
                checkpoint_model = CheckpointModel(
                    checkpoint_id=checkpoint_id,
                    checkpoint_type=checkpoint_type,
                    chat_id=chat_id,
                    last_processed_id=last_processed_id,
                    last_processed_timestamp=last_processed_timestamp,
                    total_processed=total_processed or 0,
                    last_backfill_completed=None,  # Set explicitly
                    backfill_in_progress=backfill_in_progress or False
                )
                
                checkpoint_dict = self._checkpoint_model_to_dict(checkpoint_model)
                
                def operation(client: Client) -> Any:
                    return client.table(self.table_names["checkpoints"]).upsert(
                        checkpoint_dict,
                        on_conflict="checkpoint_id"
                    )
            
            await self._execute_with_retry(
                operation,
                f"update_checkpoint_{checkpoint_type}"
            )
            
            logger.debug(f"Updated checkpoint {checkpoint_type} for chat {chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update checkpoint {checkpoint_type}: {e}")
            return False
    
    async def get_last_message_id(
        self, 
        chat_id: int
    ) -> Optional[int]:
        """
        Get the ID of the last processed message in a chat.
        
        Args:
            chat_id: Chat ID to check
            
        Returns:
            Message ID if found, None otherwise
        """
        try:
            def operation(client: Client) -> Any:
                query = client.table(self.table_names["messages"]).select("message_id")
                query = query.eq("chat_id", chat_id)
                return query.order("date", desc=True).limit(1)
            
            result = await self._execute_with_retry(
                operation,
                f"get_last_message_id_{chat_id}"
            )
            
            if result.data:
                return result.data[0]["message_id"]
            return None
            
        except Exception as e:
            logger.error(f"Failed to get last message ID for chat {chat_id}: {e}")
            return None
    
    async def store_chat_info(self, chat: Chat) -> bool:
        """
        Store or update chat information.
        
        Args:
            chat: Telegram chat object
            
        Returns:
            True if successful, False otherwise
        """
        try:
            chat_model = ChatInfoModel(
                chat_id=chat.id,
                chat_type=ChatType(str(chat.type)),
                title=getattr(chat, 'title', None),
                username=getattr(chat, 'username', None),
                first_name=getattr(chat, 'first_name', None),
                last_name=getattr(chat, 'last_name', None),
                bio=getattr(chat, 'bio', None),
                description=getattr(chat, 'description', None),
                invite_link=getattr(chat, 'invite_link', None),
                slow_mode_delay=getattr(chat, 'slow_mode_delay', None),
                message_auto_delete_time=getattr(chat, 'message_auto_delete_time', None),
                has_protected_content=getattr(chat, 'has_protected_content', None),
                has_private_forwards=getattr(chat, 'has_private_forwards', None),
                has_restricted_voice_and_video_messages=getattr(chat, 'has_restricted_voice_and_video_messages', None),
                join_to_send_messages=getattr(chat, 'join_to_send_messages', None),
                join_by_request=getattr(chat, 'join_by_request', None),
                is_forum=getattr(chat, 'is_forum', None),
                active_usernames=getattr(chat, 'active_usernames', None),
                emoji_status_custom_emoji_id=getattr(chat, 'emoji_status_custom_emoji_id', None),
                has_hidden_members=getattr(chat, 'has_hidden_members', None),
                has_aggressive_anti_spam_enabled=getattr(chat, 'has_aggressive_anti_spam_enabled', None)
            )
            
            chat_dict = self._chat_info_model_to_dict(chat_model)
            
            def operation(client: Client) -> Any:
                return client.table(self.table_names["chats"]).upsert(
                    chat_dict,
                    on_conflict="chat_id"
                )
            
            await self._execute_with_retry(
                operation,
                f"store_chat_info_{chat.id}"
            )
            
            logger.debug(f"Stored chat info for {chat.title or chat.username} ({chat.id})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store chat info for {chat.id}: {e}")
            return False
    
    async def store_user_info(self, user: User) -> bool:
        """
        Store or update user information.
        
        Args:
            user: Telegram user object
            
        Returns:
            True if successful, False otherwise
        """
        try:
            user_model = UserInfoModel(
                user_id=user.id,
                is_bot=user.is_bot,
                first_name=user.first_name,
                last_name=user.last_name,
                username=user.username,
                language_code=user.language_code,
                is_premium=getattr(user, 'is_premium', None),
                added_to_attachment_menu=getattr(user, 'added_to_attachment_menu', None),
                can_join_groups=getattr(user, 'can_join_groups', None),
                can_read_all_group_messages=getattr(user, 'can_read_all_group_messages', None),
                supports_inline_queries=getattr(user, 'supports_inline_queries', None)
            )
            
            user_dict = self._user_info_model_to_dict(user_model)
            
            def operation(client: Client) -> Any:
                return client.table(self.table_names["users"]).upsert(
                    user_dict,
                    on_conflict="user_id"
                )
            
            await self._execute_with_retry(
                operation,
                f"store_user_info_{user.id}"
            )
            
            logger.debug(f"Stored user info for {user.username or user.first_name} ({user.id})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store user info for {user.id}: {e}")
            return False
    
    def _convert_telegram_message(self, message: Message, is_backfilled: bool = False) -> MessageModel:
        """
        Convert a Telegram message to a MessageModel for database storage.
        
        Args:
            message: Telegram message object
            is_backfilled: Whether this message is being backfilled
            
        Returns:
            MessageModel instance ready for database storage
        """
        # Determine message type
        message_type = MessageType.TEXT
        if message.text:
            message_type = MessageType.TEXT
        elif message.photo:
            message_type = MessageType.PHOTO
        elif message.video:
            message_type = MessageType.VIDEO
        elif message.audio:
            message_type = MessageType.AUDIO
        elif message.document:
            message_type = MessageType.DOCUMENT
        elif message.voice:
            message_type = MessageType.VOICE
        elif message.video_note:
            message_type = MessageType.VIDEO_NOTE
        elif message.sticker:
            message_type = MessageType.STICKER
        elif message.animation:
            message_type = MessageType.ANIMATION
        elif message.contact:
            message_type = MessageType.CONTACT
        elif message.dice:
            message_type = MessageType.DICE
        elif message.game:
            message_type = MessageType.GAME
        elif message.poll:
            message_type = MessageType.POLL
        elif message.venue:
            message_type = MessageType.VENUE
        elif message.location:
            message_type = MessageType.LOCATION
        elif message.invoice:
            message_type = MessageType.INVOICE
        elif message.successful_payment:
            message_type = MessageType.SUCCESSFUL_PAYMENT
        elif message.web_app_data:
            message_type = MessageType.WEB_APP_DATA
        
        # Handle attachments
        attachments = []
        if message.document:
            attachments.append(AttachmentModel(
                file_id=message.document.file_id,
                file_unique_id=message.document.file_unique_id,
                file_name=message.document.file_name,
                mime_type=message.document.mime_type,
                file_size=message.document.file_size,
                thumb=message.document.thumb.to_dict() if message.document.thumb else None
            ))
        
        return MessageModel(
            message_id=message.message_id,
            chat_id=message.chat.id,
            from_user_id=message.from_user.id if message.from_user else None,
            text=message.text,
            message_type=message_type,
            from_user_username=message.from_user.username if message.from_user else None,
            from_user_first_name=message.from_user.first_name if message.from_user else None,
            from_user_last_name=message.from_user.last_name if message.from_user else None,
            from_user_is_bot=message.from_user.is_bot if message.from_user else False,
            from_user_language_code=message.from_user.language_code if message.from_user else None,
            date=message.date,
            edit_date=message.edit_date,
            forward_from_user_id=message.forward_from.id if message.forward_from else None,
            forward_from_chat_id=message.forward_from_chat.id if message.forward_from_chat else None,
            forward_from_message_id=message.forward_from_message_id,
            forward_signature=message.forward_signature,
            forward_sender_name=message.forward_sender_name,
            forward_date=message.forward_date,
            reply_to_message_id=message.reply_to_message.message_id if message.reply_to_message else None,
            reply_to_message=message.reply_to_message.to_dict() if message.reply_to_message else None,
            attachments=attachments,
            entities=[entity.to_dict() for entity in message.entities] if message.entities else [],
            caption_entities=[entity.to_dict() for entity in message.caption_entities] if message.caption_entities else [],
            photo=[photo.to_dict() for photo in message.photo] if message.photo else None,
            audio=message.audio.to_dict() if message.audio else None,
            document=message.document.to_dict() if message.document else None,
            video=message.video.to_dict() if message.video else None,
            voice=message.voice.to_dict() if message.voice else None,
            video_note=message.video_note.to_dict() if message.video_note else None,
            sticker=message.sticker.to_dict() if message.sticker else None,
            animation=message.animation.to_dict() if message.animation else None,
            contact=message.contact.to_dict() if message.contact else None,
            dice=message.dice.to_dict() if message.dice else None,
            game=message.game.to_dict() if message.game else None,
            poll=message.poll.to_dict() if message.poll else None,
            venue=message.venue.to_dict() if message.venue else None,
            location=message.location.to_dict() if message.location else None,
            invoice=message.invoice.to_dict() if message.invoice else None,
            successful_payment=message.successful_payment.to_dict() if message.successful_payment else None,
            web_app_data=message.web_app_data.to_dict() if message.web_app_data else None,
            new_chat_members=[member.to_dict() for member in message.new_chat_members] if message.new_chat_members else None,
            left_chat_member=message.left_chat_member.to_dict() if message.left_chat_member else None,
            new_chat_title=message.new_chat_title,
            new_chat_photo=[photo.to_dict() for photo in message.new_chat_photo] if message.new_chat_photo else None,
            delete_chat_photo=message.delete_chat_photo,
            group_chat_created=message.group_chat_created,
            supergroup_chat_created=message.supergroup_chat_created,
            channel_chat_created=message.channel_chat_created,
            message_auto_delete_time=message.message_auto_delete_time,
            migrate_to_chat_id=message.migrate_to_chat_id,
            migrate_from_chat_id=message.migrate_from_chat_id,
            pinned_message=message.pinned_message.to_dict() if message.pinned_message else None,
            reply_markup=message.reply_markup.to_dict() if message.reply_markup else None,
            is_backfilled=is_backfilled
        )
    
    @lru_cache(maxsize=128)
    def _get_cached_stats_key(self, stat_type: str) -> str:
        """Generate cache key for statistics."""
        return f"stats_{stat_type}_{int(datetime.now(timezone.utc).timestamp() // self._cache_ttl)}"
    
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get database statistics with caching.
        
        Returns:
            Dictionary containing database statistics
        """
        try:
            # Check cache validity
            now = datetime.now(timezone.utc)
            if (now - self._last_cache_update).total_seconds() < self._cache_ttl and self._stats_cache:
                return self._stats_cache
            
            stats = {}
            
            # Get message count
            def get_message_count(client: Client) -> Any:
                return client.table(self.table_names["messages"]).select("id", count="exact")
            
            result = await self._execute_with_retry(
                get_message_count,
                "get_message_count"
            )
            stats["total_messages"] = result.count
            
            # Get action count
            def get_action_count(client: Client) -> Any:
                return client.table(self.table_names["actions"]).select("id", count="exact")
            
            result = await self._execute_with_retry(
                get_action_count,
                "get_action_count"
            )
            stats["total_actions"] = result.count
            
            # Get chat count
            def get_chat_count(client: Client) -> Any:
                return client.table(self.table_names["chats"]).select("id", count="exact")
            
            result = await self._execute_with_retry(
                get_chat_count,
                "get_chat_count"
            )
            stats["total_chats"] = result.count
            
            # Update cache
            self._stats_cache = stats
            self._last_cache_update = now
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get database statistics: {e}")
            return self._stats_cache if self._stats_cache else {}
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the database.
        
        Returns:
            Dictionary containing health check results
        """
        health_status = {
            "database_connected": False,
            "tables_accessible": False,
            "last_message_timestamp": None,
            "error": None
        }
        
        try:
            # Test basic connection
            await self._test_connection()
            health_status["database_connected"] = True
            
            # Test table access
            def test_tables(client: Client) -> Any:
                return client.table(self.table_names["messages"]).select("date").order("date", desc=True).limit(1)
            
            result = await self._execute_with_retry(test_tables, "health_check_tables")
            health_status["tables_accessible"] = True
            
            if result.data:
                health_status["last_message_timestamp"] = result.data[0]["date"]
            
        except Exception as e:
            health_status["error"] = str(e)
            logger.error(f"Health check failed: {e}")
        
        return health_status
    
    async def cleanup_old_data(self, days_to_keep: int = 90) -> Dict[str, int]:
        """
        Clean up old data from the database.
        
        Args:
            days_to_keep: Number of days of data to keep
            
        Returns:
            Dictionary with cleanup results
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
        cleanup_results = {"messages_deleted": 0, "actions_deleted": 0}
        
        try:
            # Cleanup old messages
            def cleanup_messages(client: Client) -> Any:
                return client.table(self.table_names["messages"]).delete().lt("date", cutoff_date.isoformat())
            
            result = await self._execute_with_retry(cleanup_messages, "cleanup_old_messages")
            cleanup_results["messages_deleted"] = len(result.data) if result.data else 0
            
            # Cleanup old actions
            def cleanup_actions(client: Client) -> Any:
                return client.table(self.table_names["actions"]).delete().lt("occurred_at", cutoff_date.isoformat())
            
            result = await self._execute_with_retry(cleanup_actions, "cleanup_old_actions")
            cleanup_results["actions_deleted"] = len(result.data) if result.data else 0
            
            logger.info(f"Cleaned up {cleanup_results['messages_deleted']} messages and {cleanup_results['actions_deleted']} actions")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
        
        return cleanup_results
    
    async def close(self) -> None:
        """Close the database connection."""
        if self.client:
            logger.info("Closing Supabase connection")
            # Supabase client doesn't need explicit closing
            self.client = None
            self._initialized = False
    
    def _message_model_to_dict(self, message_model: MessageModel) -> Dict[str, Any]:
        """
        Convert MessageModel to a JSON-serializable dictionary for database storage.
        
        Args:
            message_model: The MessageModel to convert
            
        Returns:
            Dictionary with datetime objects converted to ISO format strings
        """
        try:
            data = message_model.model_dump()
            
            # Recursively convert all datetime objects to strings
            data = self._convert_datetime_recursive(data)
            
            # Convert enum values to strings
            if 'message_type' in data:
                if hasattr(data['message_type'], 'value'):
                    data['message_type'] = data['message_type'].value
                elif isinstance(data['message_type'], str):
                    pass
                else:
                    data['message_type'] = 'text'
            
            return data
            
        except Exception as e:
            logger.error(f"Error converting MessageModel to dict: {e}")
            raise
    
    def _convert_datetime_recursive(self, obj: Any) -> Any:
        """
        Recursively convert datetime objects to ISO format strings.
        
        Args:
            obj: The object to convert (can be dict, list, or any other type)
            
        Returns:
            The object with all datetime objects converted to strings
        """
        if isinstance(obj, dict):
            return {k: self._convert_datetime_recursive(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_datetime_recursive(item) for item in obj]
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, 'isoformat') and callable(getattr(obj, 'isoformat')):
            return obj.isoformat()
        else:
            return obj
    
    def _chat_info_model_to_dict(self, chat_model: ChatInfoModel) -> Dict[str, Any]:
        """
        Convert ChatInfoModel to a JSON-serializable dictionary for database storage.
        
        Args:
            chat_model: The ChatInfoModel to convert
            
        Returns:
            Dictionary with datetime objects converted to ISO format strings
        """
        data = chat_model.model_dump()
        
        # Convert datetime objects to ISO format strings
        if data.get('first_seen'):
            data['first_seen'] = data['first_seen'].isoformat()
        if data.get('last_updated'):
            data['last_updated'] = data['last_updated'].isoformat()
        
        # Convert enum values to strings
        data['chat_type'] = data['chat_type'].value
        
        return data
    
    def _user_info_model_to_dict(self, user_model: UserInfoModel) -> Dict[str, Any]:
        """
        Convert UserInfoModel to a JSON-serializable dictionary for database storage.
        
        Args:
            user_model: The UserInfoModel to convert
            
        Returns:
            Dictionary with datetime objects converted to ISO format strings
        """
        data = user_model.model_dump()
        
        # Convert datetime objects to ISO format strings
        if data.get('first_seen'):
            data['first_seen'] = data['first_seen'].isoformat()
        if data.get('last_updated'):
            data['last_updated'] = data['last_updated'].isoformat()
        
        return data
    
    def _checkpoint_model_to_dict(self, checkpoint_model: CheckpointModel) -> Dict[str, Any]:
        """
        Convert CheckpointModel to a JSON-serializable dictionary for database storage.
        
        Args:
            checkpoint_model: The CheckpointModel to convert
            
        Returns:
            Dictionary with datetime objects converted to ISO format strings
        """
        data = checkpoint_model.model_dump()
        
        # Convert datetime objects to ISO format strings
        if data.get('last_processed_timestamp'):
            data['last_processed_timestamp'] = data['last_processed_timestamp'].isoformat()
        if data.get('last_backfill_completed'):
            data['last_backfill_completed'] = data['last_backfill_completed'].isoformat()
        if data.get('created_at'):
            data['created_at'] = data['created_at'].isoformat()
        if data.get('updated_at'):
            data['updated_at'] = data['updated_at'].isoformat()
        
        return data
    
    def _action_model_to_dict(self, action_model: ActionModel) -> Dict[str, Any]:
        """
        Convert ActionModel to a JSON-serializable dictionary for database storage.
        
        Args:
            action_model: The ActionModel to convert
            
        Returns:
            Dictionary with datetime objects converted to ISO format strings
        """
        data = action_model.model_dump()
        
        # Convert datetime objects to ISO format strings
        if data.get('occurred_at'):
            data['occurred_at'] = data['occurred_at'].isoformat()
        if data.get('logged_at'):
            data['logged_at'] = data['logged_at'].isoformat()
        
        # Convert enum values to strings
        data['action_type'] = data['action_type'].value
        
        return data 