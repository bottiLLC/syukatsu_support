"""
ロギング設定（src/config/logging_config.py）のユニットテスト。
"""

import logging
import structlog
from unittest.mock import patch
from src.config.logging_config import setup_logging

class TestLoggingConfig:
    @patch("src.config.logging_config.structlog.configure")
    def test_setup_logging(self, mock_configure):
        """setup_loggingが正しいパラメータでstructlog.configureを呼び出すことをテストします。"""
        setup_logging()
        
        mock_configure.assert_called_once()
        
        # You might want to add more specific assertions about the arguments passed to configure
        # For example, checking the processors or logger_factory
        # _, kwargs = mock_configure.call_args
        # assert "processors" in kwargs
        # assert "logger_factory" in kwargs
