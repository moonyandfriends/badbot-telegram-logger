-- SQL script to migrate Telegram Logger database columns to BIGINT

-- Drop existing views to avoid dependency issues during column alteration
DROP VIEW IF EXISTS telegram_recent_messages CASCADE;
DROP VIEW IF EXISTS telegram_chat_message_stats CASCADE;
DROP VIEW IF EXISTS telegram_action_stats CASCADE;
DROP VIEW IF EXISTS telegram_user_activity_stats CASCADE;

-- Alter telegram_messages table
ALTER TABLE telegram_messages
ALTER COLUMN chat_id TYPE BIGINT,
ALTER COLUMN from_user_id TYPE BIGINT,
ALTER COLUMN forward_from_user_id TYPE BIGINT,
ALTER COLUMN forward_from_chat_id TYPE BIGINT,
ALTER COLUMN forward_from_message_id TYPE BIGINT,
ALTER COLUMN reply_to_message_id TYPE BIGINT;

-- Alter telegram_actions table
ALTER TABLE telegram_actions
ALTER COLUMN chat_id TYPE BIGINT,
ALTER COLUMN user_id TYPE BIGINT;

-- Alter telegram_checkpoints table
ALTER TABLE telegram_checkpoints
ALTER COLUMN chat_id TYPE BIGINT;

-- Alter telegram_chats table
ALTER TABLE telegram_chats
ALTER COLUMN chat_id TYPE BIGINT;

-- Alter telegram_users table
ALTER TABLE telegram_users
ALTER COLUMN user_id TYPE BIGINT;

-- Recreate views with updated column types
-- View for recent messages with sender information
CREATE OR REPLACE VIEW telegram_recent_messages AS
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
CREATE OR REPLACE VIEW telegram_chat_message_stats AS
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
CREATE OR REPLACE VIEW telegram_action_stats AS
SELECT 
    action_type,
    COUNT(*) as count,
    MIN(occurred_at) as first_occurrence,
    MAX(occurred_at) as last_occurrence
FROM telegram_actions
GROUP BY action_type
ORDER BY count DESC;

-- View for user activity statistics
CREATE OR REPLACE VIEW telegram_user_activity_stats AS
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
