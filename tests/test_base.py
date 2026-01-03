import pytest
from unittest.mock import patch, MagicMock

# Target Imports
from src.core.base import BaseOpenAIService
from src.config.app_config import AppConfig

# --- Fixtures ---

@pytest.fixture
def mock_openai_init():
    """Mocks the OpenAI client initialization."""
    with patch("src.core.base.OpenAI") as mock:
        yield mock

@pytest.fixture
def mock_logger():
    """Mocks the module logger."""
    with patch("src.core.base.logger") as mock:
        yield mock

# --- Test Cases ---

class TestBaseOpenAIService:
    
    def test_init_success(self, mock_openai_init):
        """
        [Init] Verify correct client initialization with config parameters.
        """
        api_key = "sk-test-key"
        
        # Instantiate the base service (or a concrete subclass)
        service = BaseOpenAIService(api_key=api_key)
        
        # Verify OpenAI client was created
        mock_openai_init.assert_called_once_with(
            api_key=api_key,
            timeout=AppConfig.API_TIMEOUT,
            max_retries=AppConfig.API_MAX_RETRIES
        )
        assert service._client == mock_openai_init.return_value

    @pytest.mark.parametrize("invalid_key", [None, ""])
    def test_init_missing_api_key(self, invalid_key, mock_openai_init, mock_logger):
        """
        [Validation] Verify ValueError is raised when API key is missing.
        """
        with pytest.raises(ValueError, match="API Key is required"):
            BaseOpenAIService(api_key=invalid_key)
        
        # Verify logging
        mock_logger.error.assert_called_once()
        assert "Attempted to initialize BaseOpenAIService without an API key" in mock_logger.error.call_args[0][0]
        
        # Verify client was NOT initialized
        mock_openai_init.assert_not_called()