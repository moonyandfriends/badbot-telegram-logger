# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Renamed environment variables for consistency:
  - `TELEGRAM_TOKEN` → `logger_telegram_token`
  - `SUPABASE_KEY` → `supabase_key`
  - `SUPABASE_URL` → `supabase_url`
- Renamed database views to use consistent `telegram_` prefix:
  - `recent_messages` → `telegram_recent_messages`
  - `chat_message_stats` → `telegram_chat_message_stats`
  - `action_stats` → `telegram_action_stats`
  - `user_activity_stats` → `telegram_user_activity_stats`

### Added
- Initial project setup with Telegram bot integration
- Supabase database integration with retry logic
- Message and action logging functionality
- Docker and docker-compose configuration
- Comprehensive test suite
- Health check endpoints
- Backfill support for existing messages
- Batch processing for improved performance

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- Added DROP VIEW statements to schema.sql to prevent conflicts when importing to existing databases
- Created cleanup.sql script for resolving database import conflicts
- Fixed deprecated `--no-dev` flag in Dockerfile for Poetry compatibility
- Fixed Docker build by copying README.md file for Poetry project installation
- Fixed Docker build by copying source code before Poetry install to resolve package installation
- Fixed Docker build by using --no-root flag to skip current project installation
- Removed unused asyncpg import from database.py to fix ModuleNotFoundError
- Fixed Docker installation to properly install the project package
- Changed Docker CMD to run bot directly with python instead of poetry run script
- Added TelegramLogger to __init__.py exports to fix import error in main.py
- Fixed python-telegram-bot API usage for newer versions (idle and stop methods)
- Fixed application running loop to use proper polling instead of idle method

### Security
- N/A 