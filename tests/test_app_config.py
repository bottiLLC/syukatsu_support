import json
import os
import pytest
from unittest.mock import MagicMock, patch, mock_open
from cryptography.fernet import Fernet

# Target Imports
from src.config.app_config import (
    AppConfig,
    UserConfig,
    SecurityManager,
    ConfigManager,
    KEY_FILE,
    CONFIG_FILE
)

# --- Fixtures ---

@pytest.fixture
def mock_fernet_key():
    """Returns a valid Fernet key for testing."""
    return Fernet.generate_key()

@pytest.fixture
def mock_key_file(mock_fernet_key):
    """Mocks the KEY_FILE Path object."""
    with patch("src.config.app_config.KEY_FILE") as mock_path:
        # Default behavior: File exists and returns a valid key
        mock_path.exists.return_value = True
        mock_path.read_bytes.return_value = mock_fernet_key
        yield mock_path

@pytest.fixture
def mock_config_file():
    """Mocks the CONFIG_FILE Path object."""
    with patch("src.config.app_config.CONFIG_FILE") as mock_path:
        yield mock_path

# --- SecurityManager Tests ---

class TestSecurityManager:

    def test_get_or_create_key_existing(self, mock_key_file, mock_fernet_key):
        """[Security] Should read key if file exists."""
        key = SecurityManager._get_or_create_key()
        assert key == mock_fernet_key
        mock_key_file.read_bytes.assert_called_once()
        mock_key_file.write_bytes.assert_not_called()

    def test_get_or_create_key_missing(self, mock_key_file):
        """[Security] Should generate and save new key if file missing."""
        mock_key_file.exists.return_value = False
        
        with patch("src.config.app_config.Fernet.generate_key", return_value=b"new_key"):
            key = SecurityManager._get_or_create_key()
            
            assert key == b"new_key"
            mock_key_file.write_bytes.assert_called_once_with(b"new_key")

    @patch("os.name", "posix")
    def test_key_permissions_posix(self, mock_key_file):
        """[Security] Should set chmod 600 on POSIX systems."""
        mock_key_file.exists.return_value = False
        SecurityManager._get_or_create_key()
        mock_key_file.chmod.assert_called_once_with(0o600)

    def test_encrypt_decrypt_flow(self, mock_key_file):
        """[Security] Happy path: Encrypt text and Decrypt it back."""
        secret = "super_secret_api_key"
        
        encrypted = SecurityManager.encrypt(secret)
        assert encrypted != secret
        assert isinstance(encrypted, str)
        assert len(encrypted) > 0
        
        decrypted = SecurityManager.decrypt(encrypted)
        assert decrypted == secret

    def test_encrypt_error_handling(self, mock_key_file):
        """[Error] Should return empty string if encryption fails."""
        # Force an error during key reading
        mock_key_file.read_bytes.side_effect = IOError("Access Denied")
        
        result = SecurityManager.encrypt("data")
        assert result == ""

    def test_decrypt_invalid_token(self, mock_key_file):
        """[Error] Should return None if token is invalid."""
        result = SecurityManager.decrypt("not_a_valid_fernet_token")
        assert result is None

# --- ConfigManager Tests ---

class TestConfigManager:

    def test_load_defaults_no_file(self, mock_config_file):
        """[Config] Should return default UserConfig if file doesn't exist."""
        mock_config_file.exists.return_value = False
        
        # Ensure no env var interference
        with patch.dict(os.environ, {}, clear=True):
            config = ConfigManager.load()
            
            assert isinstance(config, UserConfig)
            assert config.api_key is None
            assert config.model == AppConfig.DEFAULT_MODEL
            assert config.reasoning_effort == AppConfig.DEFAULT_REASONING

    def test_load_decrypts_api_key(self, mock_config_file, mock_key_file):
        """[Config] Should decrypt 'encrypted_api_key' from JSON."""
        # Create a real encrypted string using the mock key
        fernet = Fernet(mock_key_file.read_bytes.return_value)
        enc_key = fernet.encrypt(b"my-api-key").decode("utf-8")
        
        json_data = json.dumps({
            "encrypted_api_key": enc_key,
            "model": "gpt-5.2"
        })
        
        mock_config_file.exists.return_value = True
        
        # Create mock opener with data
        m_open = mock_open(read_data=json_data)
        
        # Wire up CONFIG_FILE.open to return the mock file handle
        mock_config_file.open.side_effect = m_open
        
        with patch.dict(os.environ, {}, clear=True):
            config = ConfigManager.load()
            
            assert config.api_key == "my-api-key"

    def test_load_env_var_priority(self, mock_config_file):
        """[Config] Environment variable should override file config."""
        mock_config_file.exists.return_value = False
        
        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"}):
            config = ConfigManager.load()
            assert config.api_key == "env-key"

    def test_load_safety_defaults(self, mock_config_file):
        """
        [Safety] Loading config should reset 'model' and 'reasoning_effort' 
        to defaults, ignoring saved values.
        """
        json_data = json.dumps({
            "model": "gpt-5.2-pro",          # Expensive model
            "reasoning_effort": "xhigh",     # Expensive reasoning
            "system_prompt_mode": "Fact Finding"
        })
        
        mock_config_file.exists.return_value = True
        
        # Create mock opener with data
        m_open = mock_open(read_data=json_data)
        mock_config_file.open.side_effect = m_open
        
        config = ConfigManager.load()
             
        # Assert forced reset
        assert config.model == AppConfig.DEFAULT_MODEL # gpt-5.2
        assert config.reasoning_effort == AppConfig.DEFAULT_REASONING # high
        # Assert other fields are loaded
        assert config.system_prompt_mode == "Root Cause Analysis" # App_config resets this too

    def test_save_encrypts_key(self, mock_config_file, mock_key_file):
        """
        [Security] Save should NOT write plain 'api_key'. 
        It should write 'encrypted_api_key'.
        """
        config = UserConfig(api_key="secret_key")
        
        # Mock file writing
        m_open = mock_open()
        mock_config_file.open.side_effect = m_open
        
        # We need to patch json.dump to verify what's being written easily
        # (Alternatively we could parse m_open().write calls)
        with patch("json.dump") as mock_dump:
            ConfigManager.save(config)
            
            # Verify CONFIG_FILE.open was called with "w"
            mock_config_file.open.assert_called_with("w", encoding="utf-8")
            
            # Retrieve arguments passed to json.dump(data, f, ...)
            saved_data = mock_dump.call_args[0][0]
            
            assert "api_key" not in saved_data
            assert "encrypted_api_key" in saved_data
            assert saved_data["encrypted_api_key"] != "secret_key"
            
            # Verify we can decrypt what was saved
            decrypted = SecurityManager.decrypt(saved_data["encrypted_api_key"])
            assert decrypted == "secret_key"

    def test_save_handles_io_error(self, mock_config_file):
        """[Error] Save handles IOError gracefully (logs error, doesn't crash)."""
        config = UserConfig()
        
        # Configure the mock to raise IOError when open is called
        mock_config_file.open.side_effect = IOError("Disk full")
        
        # Should not raise exception
        try:
            ConfigManager.save(config)
        except Exception as e:
            pytest.fail(f"ConfigManager.save raised exception on IOError: {e}")

# --- AppConfig Constants ---

def test_app_config_constants():
    """Verify critical default constants."""
    assert AppConfig.DEFAULT_MODEL == "gpt-5.2"
    assert AppConfig.DEFAULT_REASONING == "high"
    assert AppConfig.API_TIMEOUT > 0
    assert AppConfig.API_MAX_RETRIES >= 0