"""
Main Telegram bot implementation for logging messages and actions.

This module contains the TelegramLogger bot class that handles all Telegram events,
message logging, action tracking, and backfill capabilities with checkpoint management.
"""

import asyncio
import signal
import sys
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import deque
import gc
from aiohttp import web
import aiohttp

from telegram import Update, Message, Chat, User
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from loguru import logger

from .config import Config, get_config
from .database import SupabaseManager, DatabaseError
from .models import ActionType


class TelegramLogger:
    """
    Telegram bot for comprehensive message and action logging.
    
    This bot logs all messages and actions to a Supabase database with
    support for backfilling historical data and checkpoint management.
    """
    
    def __init__(self, config: Optional[Config] = None) -> None:
        """
        Initialize the Telegram Logger bot.
        
        Args:
            config: Configuration object, defaults to loading from environment
        """
        self.config = config or get_config()
        
        # Initialize bot application
        self.application = Application.builder().token(self.config.telegram_token).build()
        
        # Initialize components
        self.db_manager = SupabaseManager(self.config)
        
        # Queues for batch processing
        self.message_queue: deque = deque(maxlen=self.config.max_queue_size)
        self.action_queue: deque = deque(maxlen=self.config.max_queue_size)
        
        # Tracking sets for processed items with size limits
        self.processed_messages: Set[str] = set()
        self.processed_actions: Set[str] = set()
        self._max_tracked_items = 100000  # Maximum items to track
        self._cleanup_threshold = 50000   # Clean up to this many items
        
        # Backfill tracking
        self.backfill_in_progress: Dict[str, bool] = {}
        self.backfill_tasks: Dict[str, asyncio.Task] = {}
        
        # Statistics
        self.stats = {
            "messages_processed": 0,
            "actions_processed": 0,
            "errors": 0,
            "start_time": datetime.now(timezone.utc),
            "uptime_seconds": 0,
            "memory_usage_mb": 0,
            "queue_sizes": {
                "messages": 0,
                "actions": 0
            }
        }
        
        # Health check server
        self.health_app = None
        self.health_server = None
        
        # Setup logging
        self._setup_logging()
        
        # Register event handlers
        self._register_event_handlers()
        
        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()
    
    def _setup_logging(self) -> None:
        """Setup logging configuration."""
        log_level = self.config.log_level.upper()
        
        # Remove default logger
        logger.remove()
        
        # Add console logger
        logger.add(
            sys.stderr,
            level=log_level,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            colorize=True
        )
        
        # Add file logger if configured
        if self.config.log_file_path:
            logger.add(
                self.config.log_file_path,
                level=log_level,
                format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
                rotation=self.config.log_max_size,
                retention=self.config.log_backup_count,
                compression="gz"
            )
    
    def _register_event_handlers(self) -> None:
        """Register all Telegram event handlers."""
        
        # Message handler
        self.application.add_handler(
            MessageHandler(filters.ALL, self._handle_message)
        )
        
        # Error handler
        self.application.add_error_handler(self._handle_error)
    
    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle new messages."""
        logger.debug(f"_handle_message entered for update: {update.update_id}")
        if not update.message:
            logger.debug(f"Update {update.update_id}: No message object found in update.")
            return
        
        message = update.message
        
        log_prefix = f"Message {message.message_id} from chat {message.chat.id}"
        sender_info = f"user {message.from_user.id}" if message.from_user else "unknown user"
        logger.debug(f"{log_prefix}: Received message from {sender_info}. Text: {message.text[:50] + '...' if message.text else '[No Text]'}")
        
        if not await self._should_process_message(message):
            logger.debug(f"{log_prefix}: Message skipped due to processing rules.")
            return
        
        logger.debug(f"{log_prefix}: Message passed processing rules. Queuing for storage.")
        # Add to processing queue
        await self._queue_message(message)
        
        # Store chat and user info
        await self._store_chat_and_user_info(message)
    
    async def _handle_error(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle Telegram API errors."""
        logger.error(f"Telegram error: {context.error}")
        self.stats["errors"] += 1
    
    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down gracefully...")
            asyncio.create_task(self.close())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def _should_process_message(self, message: Message) -> bool:
        """
        Check if a message should be processed.
        
        Args:
            message: Telegram message to check
            
        Returns:
            True if message should be processed, False otherwise
        """
        log_prefix = f"Message {message.message_id} from chat {message.chat.id}"

        # Skip if message is None
        if not message:
            logger.debug(f"{log_prefix}: Skipped - message object is None.")
            return False
        
        # Skip if message ID already processed
        message_key = f"{message.chat.id}_{message.message_id}"
        if message_key in self.processed_messages:
            logger.debug(f"{log_prefix}: Skipped - message ID already processed.")
            return False
        
        # Check if we should process bot messages
        if message.from_user and message.from_user.is_bot and not self.config.process_bot_messages:
            logger.debug(f"{log_prefix}: Skipped - message from bot and process_bot_messages is False.")
            return False
        
        # Check if we should process channel messages
        if message.chat.type == "channel" and not self.config.process_channel_messages:
            logger.debug(f"{log_prefix}: Skipped - message from channel and process_channel_messages is False.")
            return False
        
        # Check chat filtering
        if not self.config.should_process_chat(str(message.chat.id)):
            logger.debug(f"{log_prefix}: Skipped - chat {message.chat.id} is not allowed or is ignored.")
            return False
        
        # Check channel filtering for channels
        if message.chat.type == "channel" and message.chat.username:
            if not self.config.should_process_channel(message.chat.username):
                logger.debug(f"{log_prefix}: Skipped - channel {message.chat.username} is not allowed or is ignored.")
                return False
        
        logger.debug(f"{log_prefix}: Passed all processing checks.")
        return True
    
    async def _queue_message(self, message: Message) -> None:
        """
        Add a message to the processing queue.
        
        Args:
            message: Telegram message to queue
        """
        self.message_queue.append(message)
        message_key = f"{message.chat.id}_{message.message_id}"
        self.processed_messages.add(message_key)
        
        # Process immediately if queue is full
        if len(self.message_queue) >= self.config.batch_size:
            await self._process_message_queue()
    
    async def _queue_action(
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
        after_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add an action to the processing queue.
        
        Args:
            action_type: Type of action
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
        """
        action = {
            "action_type": action_type,
            "chat_id": chat_id,
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
            "target_id": target_id,
            "target_type": target_type,
            "target_name": target_name,
            "action_data": action_data,
            "before_data": before_data,
            "after_data": after_data
        }
        
        self.action_queue.append(action)
        
        # Process immediately if queue is full
        if len(self.action_queue) >= self.config.batch_size:
            await self._process_action_queue()
    
    async def _process_message_queue(self) -> None:
        """Process all messages in the queue."""
        if not self.message_queue:
            logger.debug("Message queue is empty. Nothing to process.")
            return
        
        logger.debug(f"Processing message queue. Current size: {len(self.message_queue)}")
        
        # Get messages from queue
        messages = []
        while self.message_queue and len(messages) < self.config.batch_size:
            messages.append(self.message_queue.popleft())
        
        if not messages:
            logger.debug("No messages to process after dequeuing.")
            return
        
        logger.debug(f"Attempting to store {len(messages)} messages in batch.")
        
        try:
            # Store messages in batch
            stored_count = await self.db_manager.store_messages_batch(messages)
            self.stats["messages_processed"] += stored_count
            
            # Update checkpoints
            for message in messages:
                await self.db_manager.update_checkpoint(
                    "message",
                    last_processed_id=str(message.message_id),
                    last_processed_timestamp=message.date,
                    chat_id=message.chat.id
                )
            
            logger.debug(f"Processed {stored_count} messages from queue")
            
        except Exception as e:
            logger.error(f"Failed to process message queue: {e}")
            self.stats["errors"] += 1
    
    async def _process_action_queue(self) -> None:
        """Process all actions in the queue."""
        if not self.action_queue:
            return
        
        # Process actions one by one (they're smaller than messages)
        actions_processed = 0
        while self.action_queue:
            action = self.action_queue.popleft()
            
            try:
                success = await self.db_manager.store_action(**action)
                if success:
                    actions_processed += 1
                    
            except Exception as e:
                logger.error(f"Failed to store action: {e}")
                self.stats["errors"] += 1
        
        if actions_processed > 0:
            self.stats["actions_processed"] += actions_processed
            logger.debug(f"Processed {actions_processed} actions from queue")
    
    async def _store_chat_and_user_info(self, message: Message) -> None:
        """Store chat and user information."""
        try:
            # Store chat info
            await self.db_manager.store_chat_info(message.chat)
            
            # Store user info if available
            if message.from_user:
                await self.db_manager.store_user_info(message.from_user)
                
        except Exception as e:
            logger.error(f"Failed to store chat/user info: {e}")
    
    async def _start_backfill_all_chats(self) -> None:
        """Start backfill process for all chats."""
        # For Telegram, we need to get chats from the bot's updates
        # This is more complex than Discord since we need to track chats we've seen
        logger.info("Backfill for Telegram requires manual chat specification")
    
    async def _start_backfill_chat(self, chat_id: int) -> None:
        """
        Start backfill process for a specific chat.
        
        Args:
            chat_id: Telegram chat ID to backfill
        """
        chat_id_str = str(chat_id)
        
        if chat_id_str in self.backfill_in_progress and self.backfill_in_progress[chat_id_str]:
            logger.warning(f"Backfill already in progress for chat {chat_id}")
            return
        
        self.backfill_in_progress[chat_id_str] = True
        
        try:
            # Mark backfill as starting
            await self.db_manager.update_checkpoint(
                "backfill",
                chat_id=chat_id,
                backfill_in_progress=True
            )
            
            logger.info(f"Starting backfill for chat {chat_id}")
            
            # Get the last processed message ID from database
            last_message_id = await self.db_manager.get_last_message_id(chat_id)
            
            # Determine cutoff date for backfill
            cutoff_date = None
            if self.config.backfill_max_age_days:
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.config.backfill_max_age_days)
            
            # Backfill messages using Telegram API
            total_processed = 0
            offset_id = last_message_id if last_message_id else 0
            
            while True:
                try:
                    # Get messages from Telegram API
                    messages = await self.application.bot.get_updates(
                        offset=offset_id,
                        limit=self.config.backfill_chunk_size,
                        timeout=30
                    )
                    
                    if not messages:
                        break
                    
                    # Process messages
                    for update in messages:
                        if update.message and update.message.chat.id == chat_id:
                            # Check cutoff date
                            if cutoff_date and update.message.date < cutoff_date:
                                continue
                            
                            # Skip if we've already processed this message
                            message_key = f"{update.message.chat.id}_{update.message.message_id}"
                            if message_key in self.processed_messages:
                                continue
                            
                            # Check if we should process this message
                            if not await self._should_process_message(update.message):
                                continue
                            
                            # Store message as backfilled
                            try:
                                success = await self.db_manager.store_message(update.message, is_backfilled=True)
                                if success:
                                    total_processed += 1
                                    self.processed_messages.add(message_key)
                                    
                                    # Update checkpoint periodically
                                    if total_processed % self.config.backfill_chunk_size == 0:
                                        await self.db_manager.update_checkpoint(
                                            "backfill",
                                            last_processed_id=str(update.message.message_id),
                                            last_processed_timestamp=update.message.date,
                                            chat_id=chat_id,
                                            total_processed=total_processed
                                        )
                                        
                                        # Delay to avoid rate limiting
                                        await asyncio.sleep(self.config.backfill_delay_seconds)
                                        
                            except Exception as e:
                                logger.error(f"Failed to store backfilled message {update.message.message_id}: {e}")
                    
                    # Update offset for next batch
                    if messages:
                        offset_id = messages[-1].update_id + 1
                    
                    # Delay to avoid rate limiting
                    await asyncio.sleep(self.config.backfill_delay_seconds)
                    
                except Exception as e:
                    logger.error(f"Error during backfill batch: {e}")
                    break
            
            # Mark backfill as completed
            await self.db_manager.update_checkpoint(
                "backfill",
                chat_id=chat_id,
                backfill_in_progress=False,
                last_processed_timestamp=datetime.now(timezone.utc)
            )
            
            logger.info(f"Completed backfill for chat {chat_id}: {total_processed} messages")
            
        except Exception as e:
            logger.error(f"Backfill failed for chat {chat_id}: {e}")
            
        finally:
            self.backfill_in_progress[chat_id_str] = False
            if chat_id_str in self.backfill_tasks:
                del self.backfill_tasks[chat_id_str]
    
    async def _start_health_server(self) -> None:
        """Start the health check server."""
        try:
            self.health_app = web.Application()
            
            async def health_handler(request):
                """Health check endpoint handler."""
                health_data = await self.get_health_status()
                return web.json_response(health_data)
            
            async def stats_handler(request):
                """Statistics endpoint handler."""
                stats_data = await self.get_stats()
                return web.json_response(stats_data)
            
            async def root_handler(request):
                """Root endpoint handler."""
                return web.json_response({
                    "name": "Telegram Logger Bot",
                    "status": "running",
                    "endpoints": {
                        "health": "/health",
                        "stats": "/stats"
                    }
                })
            
            self.health_app.router.add_get('/', root_handler)
            self.health_app.router.add_get('/health', health_handler)
            self.health_app.router.add_get('/stats', stats_handler)
            
            runner = web.AppRunner(self.health_app)
            await runner.setup()
            
            # Use Railway's PORT environment variable or fallback to config
            port = int(os.environ.get('PORT', self.config.health_check_port))
            site = web.TCPSite(runner, '0.0.0.0', port)
            await site.start()
            
            logger.info(f"Health check server started on port {port}")
            
        except Exception as e:
            logger.error(f"Failed to start health check server: {e}")
    
    async def cleanup_memory(self) -> None:
        """Clean up memory periodically."""
        try:
            # Clean up tracked message/action sets if they get too large
            if len(self.processed_messages) > self._max_tracked_items:
                # Keep only the most recent items (approximate)
                messages_list = list(self.processed_messages)
                self.processed_messages = set(messages_list[-self._cleanup_threshold:])
                logger.info(f"Cleaned up processed messages tracking: {len(messages_list)} -> {len(self.processed_messages)}")
            
            if len(self.processed_actions) > self._max_tracked_items:
                actions_list = list(self.processed_actions)
                self.processed_actions = set(actions_list[-self._cleanup_threshold:])
                logger.info(f"Cleaned up processed actions tracking: {len(actions_list)} -> {len(self.processed_actions)}")
            
            # Force garbage collection
            collected = gc.collect()
            if collected > 0:
                logger.debug(f"Garbage collector freed {collected} objects")
                
        except Exception as e:
            logger.error(f"Error during memory cleanup: {e}")
    
    async def update_stats(self) -> None:
        """Update bot statistics."""
        try:
            import psutil
            import os
            
            # Update runtime stats
            uptime = (datetime.now(timezone.utc) - self.stats["start_time"]).total_seconds()
            self.stats["uptime_seconds"] = uptime
            
            # Update memory usage
            process = psutil.Process(os.getpid())
            memory_mb = process.memory_info().rss / 1024 / 1024
            self.stats["memory_usage_mb"] = round(memory_mb, 2)
            
            # Update queue sizes
            self.stats["queue_sizes"]["messages"] = len(self.message_queue)
            self.stats["queue_sizes"]["actions"] = len(self.action_queue)
            
        except ImportError:
            # psutil not available, skip memory stats
            uptime = (datetime.now(timezone.utc) - self.stats["start_time"]).total_seconds()
            self.stats["uptime_seconds"] = uptime
        except Exception as e:
            logger.error(f"Error updating stats: {e}")
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status."""
        try:
            # Database health
            db_health = await self.db_manager.health_check()
            
            # Bot health
            bot_health = {
                "bot_connected": self.application.running,
                "chat_count": len(self.backfill_in_progress),
                "user_id": str(self.application.bot.id) if self.application.bot else None,
            }
            
            # Queue health
            queue_health = {
                "message_queue_size": len(self.message_queue),
                "action_queue_size": len(self.action_queue),
                "message_queue_full": len(self.message_queue) >= self.config.max_queue_size * 0.9,
                "action_queue_full": len(self.action_queue) >= self.config.max_queue_size * 0.9,
            }
            
            # Overall health status
            overall_healthy = (
                db_health["database_connected"] and 
                bot_health["bot_connected"] and
                not queue_health["message_queue_full"] and
                not queue_health["action_queue_full"]
            )
            
            return {
                "healthy": overall_healthy,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "database": db_health,
                "bot": bot_health,
                "queues": queue_health,
                "stats": self.stats
            }
            
        except Exception as e:
            logger.error(f"Error getting health status: {e}")
            return {
                "healthy": False,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Get bot statistics.
        
        Returns:
            Dictionary containing bot statistics
        """
        uptime = datetime.now(timezone.utc) - self.stats["start_time"]
        
        return {
            "uptime_seconds": uptime.total_seconds(),
            "messages_processed": self.stats["messages_processed"],
            "actions_processed": self.stats["actions_processed"],
            "errors": self.stats["errors"],
            "chats": len(self.backfill_in_progress),
            "queue_sizes": {
                "messages": len(self.message_queue),
                "actions": len(self.action_queue)
            },
            "backfill_status": {
                chat_id: status for chat_id, status in self.backfill_in_progress.items()
            }
        }
    
    async def start(self) -> None:
        """Start the bot."""
        try:
            # Initialize database
            await self.db_manager.initialize()
            logger.info("Database initialized successfully")
            
            # Start background tasks
            asyncio.create_task(self._background_tasks())
            
            # Start health check server
            if self.config.health_check_enabled:
                await self._start_health_server()
            
            # Start backfill if enabled
            if self.config.backfill_enabled and self.config.backfill_on_startup:
                logger.info("Starting backfill process...")
                # Note: Backfill requires manual chat specification for Telegram
            
            # Start the bot
            logger.info("Starting Telegram bot...")
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()
            
            logger.info("Bot started successfully")
            
            # Keep the bot running
            while self.application.running:
                await asyncio.sleep(1)
            
        except Exception as e:
            logger.error(f"Failed to start bot: {e}")
            raise
    
    async def _background_tasks(self) -> None:
        """Run background tasks."""
        while self.application.running:
            try:
                logger.debug("Running background tasks...")
                # Process queues
                await self._process_message_queue()
                await self._process_action_queue()
                
                # Update stats
                await self.update_stats()
                
                # Cleanup memory every 10 minutes
                if self.stats["uptime_seconds"] % 600 < 30:  # Every ~10 minutes
                    await self.cleanup_memory()
                
                # Wait before next iteration
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Error in background tasks: {e}")
                await asyncio.sleep(30)
    
    async def close(self) -> None:
        """Close the bot and cleanup resources."""
        logger.info("Shutting down Telegram Logger Bot...")
        
        try:
            # Process remaining items in queues
            if self.message_queue:
                logger.info(f"Processing {len(self.message_queue)} remaining messages...")
                await self._process_message_queue()
            
            if self.action_queue:
                logger.info(f"Processing {len(self.action_queue)} remaining actions...")
                await self._process_action_queue()
            
            # Cancel any running backfill tasks
            for task in self.backfill_tasks.values():
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            
            # Close database connection
            if self.db_manager:
                await self.db_manager.close()
            
            # Stop health server
            if self.health_app:
                await self.health_app.cleanup()
            
            # Stop the bot
            if self.application.running:
                await self.application.stop()
                await self.application.shutdown()
            
            logger.info("Shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")


async def main() -> None:
    """Main entry point for the bot."""
    try:
        config = get_config()
        bot = TelegramLogger(config)
        
        logger.info("Starting Telegram Logger Bot...")
        await bot.start()
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 