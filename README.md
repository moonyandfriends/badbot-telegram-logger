# BadBot Telegram Logger

A comprehensive Telegram bot for logging messages and actions to a Supabase database, similar to the Discord logger bot.

## Features

- **Message Logging**: Captures all messages with full metadata
- **Action Tracking**: Logs user actions, edits, deletions, and other events
- **Backfill Support**: Historical data retrieval with checkpoint management
- **Health Monitoring**: Built-in health checks and statistics
- **Rate Limiting**: Configurable rate limiting to respect Telegram API limits
- **Batch Processing**: Efficient batch operations for database storage
- **Error Handling**: Robust error handling with retry logic

## Quick Start

### Prerequisites

- Python 3.10+
- Poetry (for dependency management)
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- Supabase project with database tables

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd badbot-telegram-logger
```

2. Install dependencies:
```bash
poetry install
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. Run the bot:
```bash
poetry run telegram-logger
```

## Configuration

Create a `.env` file with the following variables:

```env
# Telegram Bot Configuration
logger_telegram_token=your_telegram_bot_token_here

# Supabase Configuration
supabase_url=your_supabase_project_url_here
supabase_key=your_supabase_anon_key_here

# Logging Configuration
LOG_LEVEL=INFO
ENABLE_DEBUG=false
LOG_FILE_PATH=logs/telegram_bot.log

# Database Configuration
MAX_RETRIES=3
RETRY_DELAY=5.0
CONNECTION_TIMEOUT=30

# Backfill Configuration
BACKFILL_ENABLED=true
BACKFILL_CHUNK_SIZE=100
BACKFILL_DELAY_SECONDS=1.0
BACKFILL_MAX_AGE_DAYS=30
BACKFILL_ON_STARTUP=true

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_CALLS=30
RATE_LIMIT_WINDOW=60

# Message Processing
PROCESS_BOT_MESSAGES=true
PROCESS_SYSTEM_MESSAGES=true
PROCESS_CHANNEL_MESSAGES=true

# Channel and Chat Filtering
ALLOWED_CHATS=123456789,987654321
IGNORED_CHATS=111111111
ALLOWED_CHANNELS=channel1,channel2
IGNORED_CHANNELS=spam_channel

# Performance Configuration
BATCH_SIZE=50
FLUSH_INTERVAL=30
MAX_QUEUE_SIZE=10000

# Health Check Configuration
HEALTH_CHECK_ENABLED=true
HEALTH_CHECK_PORT=8080
```

## Database Schema

The bot requires the following tables in your Supabase database:

- `telegram_messages` - Stores all messages
- `telegram_actions` - Stores user actions and events
- `telegram_checkpoints` - Tracks processing progress
- `telegram_chats` - Stores chat information
- `telegram_users` - Stores user information

See `database/schema.sql` for the complete schema.

## API Endpoints

When health checks are enabled, the bot provides these endpoints:

- `GET /` - Basic status information
- `GET /health` - Detailed health status
- `GET /stats` - Bot statistics

## Development

### Running Tests

```bash
poetry run pytest
```

### Code Formatting

```bash
poetry run ruff check --fix
poetry run black .
```

### Type Checking

```bash
poetry run mypy src/
```

## Deployment

### Railway Deployment

1. Connect your repository to Railway
2. Set environment variables in Railway dashboard
3. Deploy automatically on push

### Docker Deployment

```bash
docker build -t telegram-logger .
docker run -d --env-file .env telegram-logger
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Environment Variables

Create a `.env` file in the project root with the following variables:

```bash
# Telegram Bot Configuration
logger_telegram_token=your_telegram_bot_token_here

# Supabase Configuration
supabase_url=your_supabase_project_url_here
supabase_key=your_supabase_anon_key_here
```

### Required Environment Variables

- `logger_telegram_token`: Your Telegram bot token from [@BotFather](https://t.me/botfather)
- `supabase_url`: Your Supabase project URL
- `supabase_key`: Your Supabase anon key (public key) 