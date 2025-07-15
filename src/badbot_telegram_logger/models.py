"""
Database models for Telegram message and action logging.

This module defines Pydantic models that represent the structure of data
stored in the Supabase database for Telegram messages, actions, and processing checkpoints.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict


class ActionType(str, Enum):
    """Enumeration of Telegram action types that can be logged."""
    
    MESSAGE_DELETE = "message_delete"
    MESSAGE_EDIT = "message_edit"
    MESSAGE_PIN = "message_pin"
    MESSAGE_UNPIN = "message_unpin"
    MEMBER_JOIN = "member_join"
    MEMBER_LEAVE = "member_leave"
    MEMBER_UPDATE = "member_update"
    MEMBER_BAN = "member_ban"
    MEMBER_UNBAN = "member_unban"
    CHAT_CREATE = "chat_create"
    CHAT_DELETE = "chat_delete"
    CHAT_UPDATE = "chat_update"
    CHAT_MIGRATE = "chat_migrate"
    VOICE_CHAT_STARTED = "voice_chat_started"
    VOICE_CHAT_ENDED = "voice_chat_ended"
    VOICE_CHAT_PARTICIPANTS_INVITED = "voice_chat_participants_invited"
    INVITE_LINK_CREATE = "invite_link_create"
    INVITE_LINK_REVOKE = "invite_link_revoke"
    STICKER_SET_ADD = "sticker_set_add"
    STICKER_SET_REMOVE = "sticker_set_remove"
    POLL_CREATE = "poll_create"
    POLL_VOTE = "poll_vote"
    DICE_ROLL = "dice_roll"
    GAME_PLAY = "game_play"
    VIDEO_CHAT_STARTED = "video_chat_started"
    VIDEO_CHAT_ENDED = "video_chat_ended"
    VIDEO_CHAT_PARTICIPANTS_INVITED = "video_chat_participants_invited"
    VIDEO_CHAT_SCHEDULED = "video_chat_scheduled"


class MessageType(str, Enum):
    """Enumeration of Telegram message types."""
    
    TEXT = "text"
    AUDIO = "audio"
    DOCUMENT = "document"
    ANIMATION = "animation"
    PHOTO = "photo"
    STICKER = "sticker"
    VIDEO = "video"
    VIDEO_NOTE = "video_note"
    VOICE = "voice"
    CONTACT = "contact"
    DICE = "dice"
    GAME = "game"
    POLL = "poll"
    VENUE = "venue"
    LOCATION = "location"
    INVOICE = "invoice"
    SUCCESSFUL_PAYMENT = "successful_payment"
    WEB_APP_DATA = "web_app_data"
    FORWARDED = "forwarded"
    REPLY = "reply"
    SERVICE = "service"


class ChatType(str, Enum):
    """Enumeration of Telegram chat types."""
    
    PRIVATE = "private"
    GROUP = "group"
    SUPERGROUP = "supergroup"
    CHANNEL = "channel"


class AttachmentModel(BaseModel):
    """Model for Telegram message attachments."""
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    file_id: str = Field(..., description="Telegram file ID")
    file_unique_id: str = Field(..., description="Telegram unique file ID")
    file_name: Optional[str] = Field(None, description="Original filename")
    mime_type: Optional[str] = Field(None, description="MIME content type")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    duration: Optional[int] = Field(None, description="Duration in seconds (for audio/video)")
    width: Optional[int] = Field(None, description="Width (for images/videos)")
    height: Optional[int] = Field(None, description="Height (for images/videos)")
    thumb: Optional[Dict[str, Any]] = Field(None, description="Thumbnail information")
    caption: Optional[str] = Field(None, description="File caption")


class MessageModel(BaseModel):
    """Model for Telegram messages stored in Supabase."""
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    # Primary identifiers
    message_id: int = Field(..., description="Telegram message ID")
    chat_id: int = Field(..., description="Telegram chat ID")
    from_user_id: Optional[int] = Field(None, description="Telegram user ID of message sender")
    
    # Message content
    text: Optional[str] = Field(None, description="Message text content")
    message_type: MessageType = Field(MessageType.TEXT, description="Type of message")
    
    # Sender information
    from_user_username: Optional[str] = Field(None, description="Username of message sender")
    from_user_first_name: Optional[str] = Field(None, description="First name of message sender")
    from_user_last_name: Optional[str] = Field(None, description="Last name of message sender")
    from_user_is_bot: bool = Field(False, description="Whether sender is a bot")
    from_user_language_code: Optional[str] = Field(None, description="Language code of sender")
    
    # Message metadata
    date: datetime = Field(..., description="When message was sent")
    edit_date: Optional[datetime] = Field(None, description="When message was last edited")
    forward_from_user_id: Optional[int] = Field(None, description="Original sender ID if forwarded")
    forward_from_chat_id: Optional[int] = Field(None, description="Original chat ID if forwarded")
    forward_from_message_id: Optional[int] = Field(None, description="Original message ID if forwarded")
    forward_signature: Optional[str] = Field(None, description="Forward signature")
    forward_sender_name: Optional[str] = Field(None, description="Forward sender name")
    forward_date: Optional[datetime] = Field(None, description="Original forward date")
    
    # Reply information
    reply_to_message_id: Optional[int] = Field(None, description="ID of replied message")
    reply_to_message: Optional[Dict[str, Any]] = Field(None, description="Replied message data")
    
    # Rich content (stored as JSONB for flexibility)
    attachments: List[AttachmentModel] = Field(default_factory=list, description="Message attachments")
    entities: List[Dict[str, Any]] = Field(default_factory=list, description="Message entities (mentions, links, etc.)")
    caption_entities: List[Dict[str, Any]] = Field(default_factory=list, description="Caption entities")
    
    # Media information
    photo: Optional[List[Dict[str, Any]]] = Field(None, description="Photo information")
    audio: Optional[Dict[str, Any]] = Field(None, description="Audio information")
    document: Optional[Dict[str, Any]] = Field(None, description="Document information")
    video: Optional[Dict[str, Any]] = Field(None, description="Video information")
    voice: Optional[Dict[str, Any]] = Field(None, description="Voice message information")
    video_note: Optional[Dict[str, Any]] = Field(None, description="Video note information")
    sticker: Optional[Dict[str, Any]] = Field(None, description="Sticker information")
    animation: Optional[Dict[str, Any]] = Field(None, description="Animation information")
    contact: Optional[Dict[str, Any]] = Field(None, description="Contact information")
    dice: Optional[Dict[str, Any]] = Field(None, description="Dice information")
    game: Optional[Dict[str, Any]] = Field(None, description="Game information")
    poll: Optional[Dict[str, Any]] = Field(None, description="Poll information")
    venue: Optional[Dict[str, Any]] = Field(None, description="Venue information")
    location: Optional[Dict[str, Any]] = Field(None, description="Location information")
    invoice: Optional[Dict[str, Any]] = Field(None, description="Invoice information")
    successful_payment: Optional[Dict[str, Any]] = Field(None, description="Payment information")
    web_app_data: Optional[Dict[str, Any]] = Field(None, description="Web app data")
    
    # Service message information
    new_chat_members: Optional[List[Dict[str, Any]]] = Field(None, description="New chat members")
    left_chat_member: Optional[Dict[str, Any]] = Field(None, description="Left chat member")
    new_chat_title: Optional[str] = Field(None, description="New chat title")
    new_chat_photo: Optional[List[Dict[str, Any]]] = Field(None, description="New chat photo")
    delete_chat_photo: Optional[bool] = Field(None, description="Chat photo deleted")
    group_chat_created: Optional[bool] = Field(None, description="Group chat created")
    supergroup_chat_created: Optional[bool] = Field(None, description="Supergroup chat created")
    channel_chat_created: Optional[bool] = Field(None, description="Channel chat created")
    message_auto_delete_time: Optional[int] = Field(None, description="Message auto delete time")
    migrate_to_chat_id: Optional[int] = Field(None, description="Migrate to chat ID")
    migrate_from_chat_id: Optional[int] = Field(None, description="Migrate from chat ID")
    pinned_message: Optional[Dict[str, Any]] = Field(None, description="Pinned message")
    invoice: Optional[Dict[str, Any]] = Field(None, description="Invoice information")
    successful_payment: Optional[Dict[str, Any]] = Field(None, description="Successful payment")
    connected_website: Optional[str] = Field(None, description="Connected website")
    passport_data: Optional[Dict[str, Any]] = Field(None, description="Passport data")
    proximity_alert_triggered: Optional[Dict[str, Any]] = Field(None, description="Proximity alert")
    video_chat_scheduled: Optional[Dict[str, Any]] = Field(None, description="Video chat scheduled")
    video_chat_started: Optional[Dict[str, Any]] = Field(None, description="Video chat started")
    video_chat_ended: Optional[Dict[str, Any]] = Field(None, description="Video chat ended")
    video_chat_participants_invited: Optional[Dict[str, Any]] = Field(None, description="Video chat participants invited")
    web_app_data: Optional[Dict[str, Any]] = Field(None, description="Web app data")
    reply_markup: Optional[Dict[str, Any]] = Field(None, description="Reply markup")
    
    # Metadata
    logged_at: datetime = Field(default_factory=datetime.utcnow, description="When message was logged to database")
    is_backfilled: bool = Field(False, description="Whether this message was backfilled")


class ActionModel(BaseModel):
    """Model for Telegram actions/events stored in Supabase."""
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    # Primary identifiers
    action_id: str = Field(..., description="Unique action ID (UUID)")
    action_type: ActionType = Field(..., description="Type of action/event")
    chat_id: Optional[int] = Field(None, description="Telegram chat ID")
    
    # Actor information
    user_id: Optional[int] = Field(None, description="User ID who performed the action")
    username: Optional[str] = Field(None, description="Username of action performer")
    first_name: Optional[str] = Field(None, description="First name of action performer")
    last_name: Optional[str] = Field(None, description="Last name of action performer")
    
    # Target information
    target_id: Optional[int] = Field(None, description="ID of target object (user, message, etc.)")
    target_type: Optional[str] = Field(None, description="Type of target object")
    target_name: Optional[str] = Field(None, description="Name of target object")
    
    # Action details
    action_data: Dict[str, Any] = Field(default_factory=dict, description="Additional action data")
    before_data: Optional[Dict[str, Any]] = Field(None, description="State before action")
    after_data: Optional[Dict[str, Any]] = Field(None, description="State after action")
    
    # Metadata
    occurred_at: datetime = Field(..., description="When the action occurred")
    logged_at: datetime = Field(default_factory=datetime.utcnow, description="When action was logged to database")
    is_backfilled: bool = Field(False, description="Whether this action was backfilled")


class CheckpointModel(BaseModel):
    """Model for tracking processing checkpoints."""
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    # Identifiers
    checkpoint_id: str = Field(..., description="Unique checkpoint ID")
    chat_id: Optional[int] = Field(None, description="Chat ID (None for global checkpoints)")
    
    # Checkpoint data
    checkpoint_type: str = Field(..., description="Type of checkpoint (message, action, etc.)")
    last_processed_id: Optional[str] = Field(None, description="Last processed item ID")
    last_processed_timestamp: Optional[datetime] = Field(None, description="Last processed timestamp")
    
    # Processing statistics
    total_processed: int = Field(0, description="Total items processed")
    last_backfill_completed: Optional[datetime] = Field(None, description="When last backfill completed")
    backfill_in_progress: bool = Field(False, description="Whether backfill is currently running")
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow, description="When checkpoint was created")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="When checkpoint was last updated")


class ChatInfoModel(BaseModel):
    """Model for Telegram chat information."""
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    chat_id: int = Field(..., description="Telegram chat ID")
    chat_type: ChatType = Field(..., description="Type of chat")
    title: Optional[str] = Field(None, description="Chat title")
    username: Optional[str] = Field(None, description="Chat username")
    first_name: Optional[str] = Field(None, description="First name (for private chats)")
    last_name: Optional[str] = Field(None, description="Last name (for private chats)")
    bio: Optional[str] = Field(None, description="Chat bio")
    description: Optional[str] = Field(None, description="Chat description")
    invite_link: Optional[str] = Field(None, description="Chat invite link")
    slow_mode_delay: Optional[int] = Field(None, description="Slow mode delay")
    message_auto_delete_time: Optional[int] = Field(None, description="Message auto delete time")
    has_protected_content: Optional[bool] = Field(None, description="Has protected content")
    has_private_forwards: Optional[bool] = Field(None, description="Has private forwards")
    has_restricted_voice_and_video_messages: Optional[bool] = Field(None, description="Has restricted voice and video messages")
    join_to_send_messages: Optional[bool] = Field(None, description="Join to send messages")
    join_by_request: Optional[bool] = Field(None, description="Join by request")
    is_forum: Optional[bool] = Field(None, description="Is forum")
    active_usernames: Optional[List[str]] = Field(None, description="Active usernames")
    emoji_status_custom_emoji_id: Optional[str] = Field(None, description="Emoji status custom emoji ID")
    has_hidden_members: Optional[bool] = Field(None, description="Has hidden members")
    has_aggressive_anti_spam_enabled: Optional[bool] = Field(None, description="Has aggressive anti spam enabled")
    
    # Metadata
    first_seen: datetime = Field(default_factory=datetime.utcnow, description="When bot first saw chat")
    last_updated: datetime = Field(default_factory=datetime.utcnow, description="When chat info was last updated")


class UserInfoModel(BaseModel):
    """Model for Telegram user information."""
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    user_id: int = Field(..., description="Telegram user ID")
    is_bot: bool = Field(False, description="Whether user is a bot")
    first_name: str = Field(..., description="User first name")
    last_name: Optional[str] = Field(None, description="User last name")
    username: Optional[str] = Field(None, description="User username")
    language_code: Optional[str] = Field(None, description="User language code")
    is_premium: Optional[bool] = Field(None, description="Whether user is premium")
    added_to_attachment_menu: Optional[bool] = Field(None, description="Added to attachment menu")
    can_join_groups: Optional[bool] = Field(None, description="Can join groups")
    can_read_all_group_messages: Optional[bool] = Field(None, description="Can read all group messages")
    supports_inline_queries: Optional[bool] = Field(None, description="Supports inline queries")
    avatar_url: Optional[str] = Field(None, description="HTTP URL to the user's profile picture")
    
    # Metadata
    first_seen: datetime = Field(default_factory=datetime.utcnow, description="When bot first saw user")
    last_updated: datetime = Field(default_factory=datetime.utcnow, description="When user info was last updated") 