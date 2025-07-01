-- Cleanup script for existing database objects
-- Run this before importing the main schema.sql if you encounter conflicts

-- Drop existing views
DROP VIEW IF EXISTS recent_messages CASCADE;
DROP VIEW IF EXISTS chat_message_stats CASCADE;
DROP VIEW IF EXISTS action_stats CASCADE;
DROP VIEW IF EXISTS user_activity_stats CASCADE;
DROP VIEW IF EXISTS telegram_recent_messages CASCADE;
DROP VIEW IF EXISTS telegram_chat_message_stats CASCADE;
DROP VIEW IF EXISTS telegram_action_stats CASCADE;
DROP VIEW IF EXISTS telegram_user_activity_stats CASCADE;

-- Drop existing tables (WARNING: This will delete all data!)
-- Uncomment these lines if you want to start fresh
-- DROP TABLE IF EXISTS telegram_messages CASCADE;
-- DROP TABLE IF EXISTS telegram_actions CASCADE;
-- DROP TABLE IF EXISTS telegram_checkpoints CASCADE;
-- DROP TABLE IF EXISTS telegram_chats CASCADE;
-- DROP TABLE IF EXISTS telegram_users CASCADE;

-- Drop existing functions
DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;

-- Drop existing triggers
DROP TRIGGER IF EXISTS update_telegram_checkpoints_updated_at ON telegram_checkpoints;
DROP TRIGGER IF EXISTS update_telegram_chats_updated_at ON telegram_chats;
DROP TRIGGER IF EXISTS update_telegram_users_updated_at ON telegram_users;

-- Note: This script will help resolve conflicts when importing the schema
-- If you want to preserve existing data, only run the DROP VIEW statements
-- If you want to start fresh, uncomment the DROP TABLE statements 