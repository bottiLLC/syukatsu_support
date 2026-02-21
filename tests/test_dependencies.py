"""
Unit tests for dependency verification module (src/config/dependencies.py).
"""

import sys
from unittest.mock import patch, MagicMock
import pytest
from src.config.dependencies import check_dependencies, REQUIRED_PACKAGES

class TestDependencyCheck:
    """
    Tests the runtime dependency check logic.
    """

    def test_missing_package_exits_app(self):
        """
        Verify that a missing package triggers an error dialog and sys.exit(1).
        """
        def mock_import_module_side_effect(name, *args, **kwargs):
            if name == "tenacity":
                raise ImportError("No module named 'tenacity'")
            return MagicMock()

        # Patch only the specific GUI call and exit to prevent real dialogs/exits
        with patch("src.config.dependencies.importlib.import_module", side_effect=mock_import_module_side_effect):
            with patch("src.config.dependencies._show_error_dialog") as mock_show_error:
                with patch("src.config.dependencies.logger.critical") as mock_logger_critical:
                    
                    with pytest.raises(SystemExit) as excinfo:
                        check_dependencies()
                        
                    assert excinfo.value.code == 1
                    
                    # 1. Logged critical error
                    mock_logger_critical.assert_called()
                    
                    # 2. Showed GUI alert
                    mock_show_error.assert_called_once()
                    title, msg = mock_show_error.call_args[0]
                    assert "Dependency Error" in title
                    assert "pip install" in msg
                    assert "tenacity" in msg

    def test_required_packages_list_integrity(self):
        """
        Ensure key libraries for the refactored app are in the required list.
        """
        assert "tenacity" in REQUIRED_PACKAGES
        assert "google.genai" in REQUIRED_PACKAGES
        assert "pydantic" in REQUIRED_PACKAGES