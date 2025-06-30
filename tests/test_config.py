"""
Tests for the configuration module.
"""

import pytest
from unittest.mock import patch
from badbot_telegram_logger.config import Config, load_config, get_config, reset_config
import os


class TestConfig:
    """Test cases for the Config class."""
    
    def test_config_validation(self):
        """Test configuration validation."""
        # Test valid configuration
        config_data = {
            "telegram_token": "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz",
            "supabase_url": "https://test.supabase.co",
            "supabase_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRlc3QiLCJyb2xlIjoiYW5vbiIsImlhdCI6MTYzNjU2NzIwMCwiZXhwIjoxOTUyMTQzMjAwfQ.test"
        }
        
        config = Config(**config_data)
        assert config.telegram_token == config_data["telegram_token"]
        assert config.supabase_url == config_data["supabase_url"]
        assert config.supabase_key == config_data["supabase_key"]
    
    def test_invalid_telegram_token(self):
        """Test invalid Telegram token validation."""
        config_data = {
            "telegram_token": "invalid",
            "supabase_url": "https://test.supabase.co",
            "supabase_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRlc3QiLCJyb2xlIjoiYW5vbiIsImlhdCI6MTYzNjU2NzIwMCwiZXhwIjoxOTUyMTQzMjAwfQ.test"
        }
        
        with pytest.raises(ValueError, match="Telegram token appears to be invalid"):
            Config(**config_data)
    
    def test_invalid_supabase_url(self):
        """Test invalid Supabase URL validation."""
        config_data = {
            "telegram_token": "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz",
            "supabase_url": "http://invalid.com",
            "supabase_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRlc3QiLCJyb2xlIjoiYW5vbiIsImlhdCI6MTYzNjU2NzIwMCwiZXhwIjoxOTUyMTQzMjAwfQ.test"
        }
        
        with pytest.raises(ValueError, match="Supabase URL must be in format"):
            Config(**config_data)
    
    def test_chat_filtering(self):
        """Test chat filtering functionality."""
        config_data = {
            "telegram_token": "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz",
            "supabase_url": "https://test.supabase.co",
            "supabase_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRlc3QiLCJyb2xlIjoiYW5vbiIsImlhdCI6MTYzNjU2NzIwMCwiZXhwIjoxOTUyMTQzMjAwfQ.test",
            "allowed_chats": "123,456,789",
            "ignored_chats": "999"
        }
        
        config = Config(**config_data)
        
        # Test allowed chats
        assert config.should_process_chat("123") is True
        assert config.should_process_chat("456") is True
        assert config.should_process_chat("789") is True
        
        # Test ignored chats
        assert config.should_process_chat("999") is False
        
        # Test other chats (should be allowed when no specific allowlist)
        assert config.should_process_chat("111") is True
    
    def test_channel_filtering(self):
        """Test channel filtering functionality."""
        config_data = {
            "telegram_token": "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz",
            "supabase_url": "https://test.supabase.co",
            "supabase_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRlc3QiLCJyb2xlIjoiYW5vbiIsImlhdCI6MTYzNjU2NzIwMCwiZXhwIjoxOTUyMTQzMjAwfQ.test",
            "allowed_channels": "channel1,channel2",
            "ignored_channels": "spam_channel"
        }
        
        config = Config(**config_data)
        
        # Test allowed channels
        assert config.should_process_channel("channel1") is True
        assert config.should_process_channel("channel2") is True
        
        # Test ignored channels
        assert config.should_process_channel("spam_channel") is False
        
        # Test other channels (should be allowed when no specific allowlist)
        assert config.should_process_channel("other_channel") is True

    def test_config_loading(self):
        """Test that configuration loads correctly from environment variables."""
        with patch.dict(os.environ, {
            'logger_telegram_token': 'test_token',
            'supabase_url': 'https://test.supabase.co',
            'supabase_key': 'test_key'
        }):
            config = Config()
            assert config.telegram_token == 'test_token'
            assert config.supabase_url == 'https://test.supabase.co'
            assert config.supabase_key == 'test_key'


class TestConfigFunctions:
    """Test cases for configuration functions."""
    
    def setup_method(self):
        """Reset config before each test."""
        reset_config()
    
    @patch('badbot_telegram_logger.config.Config')
    def test_load_config(self, mock_config_class):
        """Test load_config function."""
        mock_config = mock_config_class.return_value
        mock_config.create_directories.return_value = None
        
        config = load_config()
        
        assert config == mock_config
        mock_config.create_directories.assert_called_once()
    
    @patch('badbot_telegram_logger.config.load_config')
    def test_get_config(self, mock_load_config):
        """Test get_config function."""
        mock_config = mock_load_config.return_value
        
        # First call should load config
        config1 = get_config()
        assert config1 == mock_config
        mock_load_config.assert_called_once()
        
        # Second call should return cached config
        config2 = get_config()
        assert config2 == mock_config
        # Should not call load_config again
        assert mock_load_config.call_count == 1
    
    def test_reset_config(self):
        """Test reset_config function."""
        # Set a mock config
        with patch('badbot_telegram_logger.config._config', 'mock_config'):
            reset_config()
            from badbot_telegram_logger.config import _config
            assert _config is None 