"""
BadBot Telegram Logger - A comprehensive Telegram bot for logging messages and actions to Supabase.

This package provides a complete solution for archiving Telegram messages and user actions
to a Supabase database with support for backfilling, health monitoring, and efficient
batch processing.
"""

__version__ = "0.1.0"
__author__ = "BadBot Team"
__description__ = "Telegram message and action logging bot"

from .config import Config, load_config, get_config
from .models import ActionType, MessageType
from .database import SupabaseManager, DatabaseError
from .bot import TelegramLogger

__all__ = [
    "Config",
    "load_config", 
    "get_config",
    "ActionType",
    "MessageType",
    "SupabaseManager",
    "DatabaseError",
    "TelegramLogger",
] 