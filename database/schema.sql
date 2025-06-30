-- Database schema for BadBot Telegram Logger
-- This file contains all the table definitions needed for the Telegram logging system

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table for storing Telegram messages
CREATE TABLE IF NOT EXISTS telegram_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    message_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    from_user_id INTEGER,
    text TEXT,
    message_type TEXT DEFAULT 'text',
    
    -- Sender information
    from_user_username TEXT,
    from_user_first_name TEXT,
    from_user_last_name TEXT,
    from_user_is_bot BOOLEAN DEFAULT FALSE,
    from_user_language_code TEXT,
    
    -- Message metadata
    date TIMESTAMPTZ NOT NULL,
    edit_date TIMESTAMPTZ,
    forward_from_user_id INTEGER,
    forward_from_chat_id INTEGER,
    forward_from_message_id INTEGER,
    forward_signature TEXT,
    forward_sender_name TEXT,
    forward_date TIMESTAMPTZ,
    
    -- Reply information
    reply_to_message_id INTEGER,
    reply_to_message JSONB,
    
    -- Rich content (stored as JSONB for flexibility)
    attachments JSONB DEFAULT '[]'::jsonb,
    entities JSONB DEFAULT '[]'::jsonb,
    caption_entities JSONB DEFAULT '[]'::jsonb,
    
    -- Media information
    photo JSONB,
    audio JSONB,
    document JSONB,
    video JSONB,
    voice JSONB,
    video_note JSONB,
    sticker JSONB,
    animation JSONB,
    contact JSONB,
    dice JSONB,
    game JSONB,
    poll JSONB,
    venue JSONB,
    location JSONB,
    invoice JSONB,
    successful_payment JSONB,
    web_app_data JSONB,
    
    -- Service message information
    new_chat_members JSONB,
    left_chat_member JSONB,
    new_chat_title TEXT,
    new_chat_photo JSONB,
    delete_chat_photo BOOLEAN,
    group_chat_created BOOLEAN,
    supergroup_chat_created BOOLEAN,
    channel_chat_created BOOLEAN,
    message_auto_delete_time INTEGER,
    migrate_to_chat_id INTEGER,
    migrate_from_chat_id INTEGER,
    pinned_message JSONB,
    reply_markup JSONB,
    
    -- Metadata
    logged_at TIMESTAMPTZ DEFAULT NOW(),
    is_backfilled BOOLEAN DEFAULT FALSE,
        
    -- Indexes for common queries
    CONSTRAINT telegram_messages_message_id_chat_id_key UNIQUE (message_id, chat_id)
);

-- Indexes for messages table
CREATE INDEX IF NOT EXISTS idx_telegram_messages_chat_id ON telegram_messages (chat_id);
CREATE INDEX IF NOT EXISTS idx_telegram_messages_from_user_id ON telegram_messages (from_user_id);
CREATE INDEX IF NOT EXISTS idx_telegram_messages_date ON telegram_messages (date);
CREATE INDEX IF NOT EXISTS idx_telegram_messages_logged_at ON telegram_messages (logged_at);
CREATE INDEX IF NOT EXISTS idx_telegram_messages_is_backfilled ON telegram_messages (is_backfilled);
CREATE INDEX IF NOT EXISTS idx_telegram_messages_message_type ON telegram_messages (message_type);

-- Table for storing Telegram actions/events
CREATE TABLE IF NOT EXISTS telegram_actions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    action_id TEXT NOT NULL UNIQUE,
    action_type TEXT NOT NULL,
    chat_id INTEGER,
    
    -- Actor information
    user_id INTEGER,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    
    -- Target information
    target_id INTEGER,
    target_type TEXT,
    target_name TEXT,
    
    -- Action details (stored as JSONB for flexibility)
    action_data JSONB DEFAULT '{}'::jsonb,
    before_data JSONB,
    after_data JSONB,
    
    -- Metadata
    occurred_at TIMESTAMPTZ NOT NULL,
    logged_at TIMESTAMPTZ DEFAULT NOW(),
    is_backfilled BOOLEAN DEFAULT FALSE,
    
    CONSTRAINT telegram_actions_action_id_key UNIQUE (action_id)
);

-- Indexes for actions table
CREATE INDEX IF NOT EXISTS idx_telegram_actions_action_type ON telegram_actions (action_type);
CREATE INDEX IF NOT EXISTS idx_telegram_actions_chat_id ON telegram_actions (chat_id);
CREATE INDEX IF NOT EXISTS idx_telegram_actions_user_id ON telegram_actions (user_id);
CREATE INDEX IF NOT EXISTS idx_telegram_actions_occurred_at ON telegram_actions (occurred_at);
CREATE INDEX IF NOT EXISTS idx_telegram_actions_is_backfilled ON telegram_actions (is_backfilled);

-- Table for tracking processing checkpoints
CREATE TABLE IF NOT EXISTS telegram_checkpoints (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    checkpoint_id TEXT NOT NULL UNIQUE,
    chat_id INTEGER,
    
    -- Checkpoint data
    checkpoint_type TEXT NOT NULL,
    last_processed_id TEXT,
    last_processed_timestamp TIMESTAMPTZ,
    
    -- Processing statistics
    total_processed INTEGER DEFAULT 0,
    last_backfill_completed TIMESTAMPTZ,
    backfill_in_progress BOOLEAN DEFAULT FALSE,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT telegram_checkpoints_checkpoint_id_key UNIQUE (checkpoint_id)
);

-- Indexes for checkpoints table
CREATE INDEX IF NOT EXISTS idx_telegram_checkpoints_type ON telegram_checkpoints (checkpoint_type);
CREATE INDEX IF NOT EXISTS idx_telegram_checkpoints_chat_id ON telegram_checkpoints (chat_id);
CREATE INDEX IF NOT EXISTS idx_telegram_checkpoints_updated_at ON telegram_checkpoints (updated_at);

-- Table for storing Telegram chat information
CREATE TABLE IF NOT EXISTS telegram_chats (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chat_id INTEGER NOT NULL UNIQUE,
    chat_type TEXT NOT NULL,
    title TEXT,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    bio TEXT,
    description TEXT,
    invite_link TEXT,
    slow_mode_delay INTEGER,
    message_auto_delete_time INTEGER,
    has_protected_content BOOLEAN,
    has_private_forwards BOOLEAN,
    has_restricted_voice_and_video_messages BOOLEAN,
    join_to_send_messages BOOLEAN,
    join_by_request BOOLEAN,
    is_forum BOOLEAN,
    active_usernames TEXT[],
    emoji_status_custom_emoji_id TEXT,
    has_hidden_members BOOLEAN,
    has_aggressive_anti_spam_enabled BOOLEAN,
    
    -- Metadata
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT telegram_chats_chat_id_key UNIQUE (chat_id)
);

-- Indexes for chats table
CREATE INDEX IF NOT EXISTS idx_telegram_chats_chat_id ON telegram_chats (chat_id);
CREATE INDEX IF NOT EXISTS idx_telegram_chats_chat_type ON telegram_chats (chat_type);
CREATE INDEX IF NOT EXISTS idx_telegram_chats_username ON telegram_chats (username);
CREATE INDEX IF NOT EXISTS idx_telegram_chats_last_updated ON telegram_chats (last_updated);
CREATE INDEX IF NOT EXISTS idx_telegram_chats_updated_at ON telegram_chats (updated_at);

-- Table for storing Telegram user information
CREATE TABLE IF NOT EXISTS telegram_users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id INTEGER NOT NULL UNIQUE,
    is_bot BOOLEAN DEFAULT FALSE,
    first_name TEXT NOT NULL,
    last_name TEXT,
    username TEXT,
    language_code TEXT,
    is_premium BOOLEAN,
    added_to_attachment_menu BOOLEAN,
    can_join_groups BOOLEAN,
    can_read_all_group_messages BOOLEAN,
    supports_inline_queries BOOLEAN,
    
    -- Metadata
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT telegram_users_user_id_key UNIQUE (user_id)
);

-- Indexes for users table
CREATE INDEX IF NOT EXISTS idx_telegram_users_user_id ON telegram_users (user_id);
CREATE INDEX IF NOT EXISTS idx_telegram_users_username ON telegram_users (username);
CREATE INDEX IF NOT EXISTS idx_telegram_users_is_bot ON telegram_users (is_bot);
CREATE INDEX IF NOT EXISTS idx_telegram_users_last_updated ON telegram_users (last_updated);
CREATE INDEX IF NOT EXISTS idx_telegram_users_updated_at ON telegram_users (updated_at);

-- Function to automatically update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers to automatically update updated_at columns
CREATE OR REPLACE TRIGGER update_telegram_checkpoints_updated_at
    BEFORE UPDATE ON telegram_checkpoints
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE OR REPLACE TRIGGER update_telegram_chats_updated_at
    BEFORE UPDATE ON telegram_chats
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE OR REPLACE TRIGGER update_telegram_users_updated_at
    BEFORE UPDATE ON telegram_users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Row Level Security (RLS) policies (optional, for additional security)
-- Uncomment these if you want to enable RLS

-- ALTER TABLE telegram_messages ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE telegram_actions ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE telegram_checkpoints ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE telegram_chats ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE telegram_users ENABLE ROW LEVEL SECURITY;

-- Create policies for service role access
-- CREATE POLICY "Service role can access telegram_messages" ON telegram_messages
--     FOR ALL USING (auth.role() = 'service_role');

-- CREATE POLICY "Service role can access telegram_actions" ON telegram_actions
--     FOR ALL USING (auth.role() = 'service_role');

-- CREATE POLICY "Service role can access telegram_checkpoints" ON telegram_checkpoints
--     FOR ALL USING (auth.role() = 'service_role');

-- CREATE POLICY "Service role can access telegram_chats" ON telegram_chats
--     FOR ALL USING (auth.role() = 'service_role');

-- CREATE POLICY "Service role can access telegram_users" ON telegram_users
--     FOR ALL USING (auth.role() = 'service_role');

-- Create some useful views for common queries

-- Drop existing views if they exist to avoid conflicts
DROP VIEW IF EXISTS recent_messages CASCADE;
DROP VIEW IF EXISTS chat_message_stats CASCADE;
DROP VIEW IF EXISTS action_stats CASCADE;
DROP VIEW IF EXISTS user_activity_stats CASCADE;

-- View for recent messages with sender information
CREATE OR REPLACE VIEW recent_messages AS
SELECT 
    m.message_id,
    m.text,
    m.from_user_username,
    m.from_user_first_name,
    m.from_user_last_name,
    m.date,
    c.title as chat_title,
    c.username as chat_username,
    c.chat_type
FROM telegram_messages m
LEFT JOIN telegram_chats c ON m.chat_id = c.chat_id
ORDER BY m.date DESC;

-- View for message statistics by chat
CREATE OR REPLACE VIEW chat_message_stats AS
SELECT 
    c.chat_id,
    c.title as chat_title,
    c.username as chat_username,
    c.chat_type,
    COUNT(m.id) as message_count,
    COUNT(DISTINCT m.from_user_id) as unique_senders,
    MIN(m.date) as first_message,
    MAX(m.date) as last_message
FROM telegram_chats c
LEFT JOIN telegram_messages m ON c.chat_id = m.chat_id
GROUP BY c.chat_id, c.title, c.username, c.chat_type;

-- View for action statistics
CREATE OR REPLACE VIEW action_stats AS
SELECT 
    action_type,
    COUNT(*) as count,
    MIN(occurred_at) as first_occurrence,
    MAX(occurred_at) as last_occurrence
FROM telegram_actions
GROUP BY action_type
ORDER BY count DESC;

-- View for user activity statistics
CREATE OR REPLACE VIEW user_activity_stats AS
SELECT 
    u.user_id,
    u.username,
    u.first_name,
    u.last_name,
    u.is_bot,
    COUNT(m.id) as messages_sent,
    MIN(m.date) as first_message,
    MAX(m.date) as last_message
FROM telegram_users u
LEFT JOIN telegram_messages m ON u.user_id = m.from_user_id
GROUP BY u.user_id, u.username, u.first_name, u.last_name, u.is_bot
ORDER BY messages_sent DESC;

-- Comments for documentation
COMMENT ON TABLE telegram_messages IS 'Stores all Telegram messages with full metadata and content';
COMMENT ON TABLE telegram_actions IS 'Stores Telegram actions and events like member joins, message edits, etc.';
COMMENT ON TABLE telegram_checkpoints IS 'Tracks processing progress for backfill and real-time operations';
COMMENT ON TABLE telegram_chats IS 'Stores Telegram chat (group/channel) information';
COMMENT ON TABLE telegram_users IS 'Stores Telegram user information';

COMMENT ON COLUMN telegram_messages.is_backfilled IS 'Indicates if this message was added during backfill process';
COMMENT ON COLUMN telegram_actions.is_backfilled IS 'Indicates if this action was added during backfill process';
COMMENT ON COLUMN telegram_checkpoints.backfill_in_progress IS 'Indicates if backfill is currently running for this checkpoint'; 