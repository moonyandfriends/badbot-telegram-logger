#!/usr/bin/env python3
"""
Main entry point for the BadBot Telegram Logger.

This script initializes and runs the Telegram bot for logging messages and actions
to a Supabase database with comprehensive backfill and checkpoint capabilities.
"""

import asyncio
import sys
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from badbot_telegram_logger import TelegramLogger
from badbot_telegram_logger.config import load_config


async def main() -> None:
    """Main entry point for the Telegram Logger Bot."""
    try:
        # Load configuration
        print("Loading configuration...")
        config = load_config()
        print(f"Configuration loaded successfully")
        print(f"Bot will connect to {len(config.allowed_chats_list) if config.allowed_chats_list else 'all'} chats")
        print(f"Backfill enabled: {config.backfill_enabled}")
        
        # Initialize and start bot
        print("Initializing Telegram bot...")
        bot = TelegramLogger(config)
        
        print("Starting bot...")
        print("Press Ctrl+C to stop the bot gracefully")
        
        await bot.start()
        
    except KeyboardInterrupt:
        print("\nReceived keyboard interrupt, shutting down gracefully...")
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        print("Bot shutdown complete")


if __name__ == "__main__":
    # Run the bot
    asyncio.run(main()) 