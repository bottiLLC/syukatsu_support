"""
Unit tests for logging configuration (src/config/logging_config.py).
"""

import logging
from unittest.mock import patch
from src.config.logging_config import setup_logging, LOG_LEVEL, LOG_FORMAT

def test_setup_logging_calls_basic_config():
    """
    Verify that setup_logging calls logging.basicConfig with expected parameters.
    """
    with patch("logging.basicConfig") as mock_basic_config:
        setup_logging()
        
        mock_basic_config.assert_called_once()
        _, kwargs = mock_basic_config.call_args
        
        assert kwargs["level"] == LOG_LEVEL
        assert kwargs["format"] == LOG_FORMAT
        assert "datefmt" in kwargs

def test_logger_retrieval():
    """Verify that we can retrieve the logger by name."""
    # Ensure setup doesn't crash
    setup_logging()
    
    logger = logging.getLogger("src.config.logging_config")
    assert isinstance(logger, logging.Logger)
    # Note: We can't easily assert the level of a specific logger if basicConfig 
    # was already called by pytest or other modules, but we check instantiation.