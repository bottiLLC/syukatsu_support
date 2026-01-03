import logging
import pytest
from unittest.mock import patch

# Target Import
from src.config.logging_config import (
    setup_logging,
    LOG_LEVEL,
    LOG_FORMAT,
    DATE_FORMAT
)

class TestLoggingConfig:
    
    def test_setup_logging_calls_basic_config(self):
        """
        [Config] Verify setup_logging calls basicConfig with correct parameters.
        """
        # Patch logging.basicConfig to prevent actual configuration changes during test
        with patch("logging.basicConfig") as mock_basic_config:
            setup_logging()
            
            mock_basic_config.assert_called_once_with(
                level=LOG_LEVEL,
                format=LOG_FORMAT,
                datefmt=DATE_FORMAT
            )

    def test_constants_values(self):
        """
        [Sanity] Verify logging constants have expected default values.
        """
        assert LOG_LEVEL == logging.INFO
        assert "%(asctime)s" in LOG_FORMAT
        assert "%Y-%m-%d" in DATE_FORMAT