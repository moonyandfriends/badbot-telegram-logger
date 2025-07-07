"""
Configuration management for Telegram Logger Bot.

This module handles all configuration settings, environment variables,
and provides validation for required settings.
"""

import os
from pathlib import Path
from typing import Optional, List
from enum import Enum

from pydantic import BaseModel, Field, field_validator, ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict


class LogLevel(str, Enum):
    """Valid log levels."""
    
    CRITICAL = "CRITICAL"
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"
    DEBUG = "DEBUG"


class Config(BaseSettings):
    """
    Configuration settings for the Telegram Logger Bot.
    
    Settings are loaded from environment variables and .env files.
    Environment variables take precedence over .env file values.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="forbid",
        validate_assignment=True
    )
    
    # Telegram Bot Configuration
    telegram_token: str = Field(..., description="Telegram bot token", alias="logger_telegram_token")
    
    # Supabase Configuration
    supabase_url: str = Field(..., description="Supabase project URL", alias="supabase_url")
    supabase_key: str = Field(..., description="Supabase anon key", alias="supabase_key")
    supabase_service_role_key: Optional[str] = Field(None, description="Supabase service role key (for admin operations)", alias="SUPABASE_SERVICE_ROLE_KEY")
    
    # Logging Configuration
    log_level: LogLevel = Field(LogLevel.INFO, description="Logging level", alias="LOG_LEVEL")
    enable_debug: bool = Field(False, description="Enable debug mode", alias="ENABLE_DEBUG")
    log_file_path: Optional[str] = Field(None, description="Path to log file", alias="LOG_FILE_PATH")
    log_max_size: int = Field(10_000_000, description="Maximum log file size in bytes", alias="LOG_MAX_SIZE")
    log_backup_count: int = Field(5, description="Number of log backups to keep", alias="LOG_BACKUP_COUNT")
    
    # Database Configuration
    max_retries: int = Field(3, description="Maximum number of database operation retries", alias="MAX_RETRIES")
    retry_delay: float = Field(5.0, description="Delay between retries in seconds", alias="RETRY_DELAY")
    connection_timeout: int = Field(30, description="Database connection timeout in seconds", alias="CONNECTION_TIMEOUT")
    
    # Backfill Configuration
    backfill_enabled: bool = Field(True, description="Enable automatic backfilling", alias="BACKFILL_ENABLED")
    backfill_chunk_size: int = Field(100, description="Number of messages to process per chunk during backfill", alias="BACKFILL_CHUNK_SIZE")
    backfill_delay_seconds: float = Field(1.0, description="Delay between backfill chunks in seconds", alias="BACKFILL_DELAY_SECONDS")
    backfill_max_age_days: Optional[int] = Field(None, description="Maximum age of messages to backfill (None for all)", alias="BACKFILL_MAX_AGE_DAYS")
    backfill_on_startup: bool = Field(True, description="Run backfill on bot startup", alias="BACKFILL_ON_STARTUP")
    
    # Rate Limiting Configuration
    rate_limit_enabled: bool = Field(True, description="Enable rate limiting", alias="RATE_LIMIT_ENABLED")
    rate_limit_calls: int = Field(30, description="Number of API calls per window", alias="RATE_LIMIT_CALLS")
    rate_limit_window: int = Field(60, description="Rate limit window in seconds", alias="RATE_LIMIT_WINDOW")
    
    # Message Processing Configuration
    process_bot_messages: bool = Field(True, description="Process messages from other bots", alias="PROCESS_BOT_MESSAGES")
    process_system_messages: bool = Field(True, description="Process system messages", alias="PROCESS_SYSTEM_MESSAGES")
    process_channel_messages: bool = Field(True, description="Process channel messages", alias="PROCESS_CHANNEL_MESSAGES")
    
    # Chat and Channel Filtering
    allowed_chats: Optional[str] = Field(None, description="Comma-separated list of chat IDs to monitor", alias="ALLOWED_CHATS")
    ignored_chats: str = Field("", description="Comma-separated list of chat IDs to ignore", alias="IGNORED_CHATS")
    allowed_channels: Optional[str] = Field(None, description="Comma-separated list of channel usernames to monitor", alias="ALLOWED_CHANNELS")
    ignored_channels: str = Field("", description="Comma-separated list of channel usernames to ignore", alias="IGNORED_CHANNELS")
    
    # Performance Configuration
    batch_size: int = Field(5, description="Batch size for database operations", alias="BATCH_SIZE")
    flush_interval: int = Field(5, description="Interval to flush pending operations in seconds", alias="FLUSH_INTERVAL")
    max_queue_size: int = Field(10000, description="Maximum size of message queue", alias="MAX_QUEUE_SIZE")
    
    # Health Check Configuration
    health_check_enabled: bool = Field(True, description="Enable health check endpoint", alias="HEALTH_CHECK_ENABLED")
    health_check_port: int = Field(8080, description="Port for health check server", alias="HEALTH_CHECK_PORT")
    
    # Metrics Configuration
    metrics_enabled: bool = Field(False, description="Enable metrics collection", alias="METRICS_ENABLED")
    metrics_port: int = Field(9090, description="Port for metrics server", alias="METRICS_PORT")
    
    @field_validator("telegram_token")
    @classmethod
    def validate_telegram_token(cls, v: str) -> str:
        """Validate Telegram token format."""
        if not v or len(v) < 40:
            raise ValueError("Telegram token appears to be invalid (too short)")
        return v
    
    @field_validator("supabase_url")
    @classmethod
    def validate_supabase_url(cls, v: str) -> str:
        """Validate Supabase URL format."""
        if not v.startswith(("https://", "http://")):
            raise ValueError("Supabase URL must start with https:// or http://")
        
        # Basic URL format validation
        if not v.replace("https://", "").replace("http://", "").strip():
            raise ValueError("Supabase URL must contain a valid domain")
            
        return v
    
    @field_validator("supabase_key")
    @classmethod
    def validate_supabase_key(cls, v: str) -> str:
        """Validate Supabase key format."""
        if not v or len(v) < 100:
            raise ValueError("Supabase key appears to be invalid (too short)")
        return v
    
    @field_validator("backfill_chunk_size")
    @classmethod
    def validate_backfill_chunk_size(cls, v: int) -> int:
        """Validate backfill chunk size."""
        if v < 1 or v > 1000:
            raise ValueError("Backfill chunk size must be between 1 and 1000")
        return v
    
    @field_validator("batch_size")
    @classmethod
    def validate_batch_size(cls, v: int) -> int:
        """Validate batch size."""
        if v < 1 or v > 500:
            raise ValueError("Batch size must be between 1 and 500")
        return v
    
    @field_validator("max_retries")
    @classmethod
    def validate_max_retries(cls, v: int) -> int:
        """Validate max retries."""
        if v < 1 or v > 10:
            raise ValueError("Max retries must be between 1 and 10")
        return v
    
    @field_validator("retry_delay")
    @classmethod
    def validate_retry_delay(cls, v: float) -> float:
        """Validate retry delay."""
        if v < 0.1 or v > 60.0:
            raise ValueError("Retry delay must be between 0.1 and 60.0 seconds")
        return v
    
    @field_validator("health_check_port", "metrics_port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate port numbers."""
        if v < 1024 or v > 65535:
            raise ValueError("Port must be between 1024 and 65535")
        return v
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return not self.enable_debug and self.log_level in (LogLevel.INFO, LogLevel.WARNING, LogLevel.ERROR)
    
    @property
    def allowed_chats_list(self) -> List[str]:
        """Get allowed chats as a list."""
        if not self.allowed_chats:
            return []
        return [item.strip() for item in self.allowed_chats.split(",") if item.strip()]
    
    @property
    def ignored_chats_list(self) -> List[str]:
        """Get ignored chats as a list."""
        if not self.ignored_chats:
            return []
        return [item.strip() for item in self.ignored_chats.split(",") if item.strip()]
    
    @property
    def allowed_channels_list(self) -> List[str]:
        """Get allowed channels as a list."""
        if not self.allowed_channels:
            return []
        return [item.strip() for item in self.allowed_channels.split(",") if item.strip()]
    
    @property
    def ignored_channels_list(self) -> List[str]:
        """Get ignored channels as a list."""
        if not self.ignored_channels:
            return []
        return [item.strip() for item in self.ignored_channels.split(",") if item.strip()]
    
    def should_process_chat(self, chat_id: str) -> bool:
        """Check if a chat should be processed."""
        if chat_id in self.ignored_chats_list:
            return False
        if not self.allowed_chats_list:
            return True
        return chat_id in self.allowed_chats_list
    
    def should_process_channel(self, channel_username: str) -> bool:
        """Check if a channel should be processed."""
        if channel_username in self.ignored_channels_list:
            return False
        if not self.allowed_channels_list:
            return True
        return channel_username in self.allowed_channels_list
    
    def get_database_table_names(self) -> dict[str, str]:
        """Get database table names for different data types."""
        return {
            "messages": "telegram_messages",
            "actions": "telegram_actions", 
            "checkpoints": "telegram_checkpoints",
            "chats": "telegram_chats",
            "users": "telegram_users",
        }
    
    def validate_required_permissions(self) -> List[str]:
        """Return list of required Telegram bot permissions."""
        permissions = [
            "read_messages",
            "read_message_history",
            "view_channel",
        ]
        
        if self.backfill_enabled:
            permissions.extend([
                "read_message_history",
            ])
        
        return permissions
    
    def create_directories(self) -> None:
        """Create necessary directories for logs and data."""
        if self.log_file_path:
            Path(self.log_file_path).parent.mkdir(parents=True, exist_ok=True)
    
    def get_log_file_path(self) -> Optional[Path]:
        """Get log file path as Path object."""
        if self.log_file_path:
            return Path(self.log_file_path)
        return None


def load_config() -> Config:
    """
    Load and validate configuration from environment variables and .env files.
    
    Returns:
        Config: Validated configuration object
        
    Raises:
        ValueError: If required configuration is missing or invalid
        ValidationError: If configuration validation fails
    """
    try:
        # Try to load configuration - BaseSettings automatically loads from env vars
        config = Config()  # type: ignore[call-arg]
        
        # Create necessary directories
        config.create_directories()
        
        return config
        
    except Exception as e:
        raise ValueError(f"Failed to load configuration: {e}") from e


def load_config_with_overrides(**overrides) -> Config:
    """
    Load configuration with specific overrides for testing.
    
    Args:
        **overrides: Configuration values to override
        
    Returns:
        Config: Configuration object with overrides
    """
    try:
        # Create config with overrides
        config = Config(**overrides)
        config.create_directories()
        return config
    except Exception as e:
        raise ValueError(f"Failed to load configuration with overrides: {e}") from e


# Global configuration instance
_config: Optional[Config] = None


def get_config() -> Config:
    """
    Get the global configuration instance.
    
    Returns:
        Config: The configuration object
        
    Raises:
        ValueError: If configuration hasn't been loaded
    """
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reload_config() -> Config:
    """
    Reload the configuration from environment variables and files.
    
    Returns:
        Config: The new configuration object
    """
    global _config
    _config = load_config()
    return _config


def reset_config() -> None:
    """Reset the global configuration instance (useful for testing)."""
    global _config
    _config = None 