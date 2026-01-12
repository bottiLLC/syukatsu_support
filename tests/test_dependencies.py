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

    def test_all_packages_present(self):
        """
        Verify that if all packages are importable, no error is raised and app continues.
        """
        # We assume the test environment itself has the packages, 
        # or we mock __import__ to always succeed.
        with patch("builtins.__import__") as mock_import:
            check_dependencies()
            
            # Verify it tried to import every required package
            for pkg in REQUIRED_PACKAGES:
                mock_import.assert_any_call(pkg)

    def test_missing_package_exits_app(self):
        """
        Verify that a missing package triggers an error dialog and sys.exit(1).
        """
        # Simulate 'tenacity' being missing
        original_import = __import__
        
        def mock_import_side_effect(name, *args, **kwargs):
            if name == "tenacity":
                raise ImportError("No module named 'tenacity'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import_side_effect):
            with patch("tkinter.messagebox.showerror") as mock_showerror:
                with patch("sys.exit") as mock_exit:
                    with patch("src.config.dependencies.logger") as mock_logger:
                        
                        check_dependencies()
                        
                        # 1. Logged critical error
                        mock_logger.critical.assert_called()
                        
                        # 2. Showed GUI alert
                        mock_showerror.assert_called_once()
                        title, msg = mock_showerror.call_args[0]
                        assert "Dependency Error" in title
                        assert "pip install" in msg
                        assert "tenacity" in msg
                        
                        # 3. Exited
                        mock_exit.assert_called_once_with(1)

    def test_required_packages_list_integrity(self):
        """
        Ensure key libraries for the refactored app are in the required list.
        """
        assert "tenacity" in REQUIRED_PACKAGES
        assert "openai" in REQUIRED_PACKAGES
        assert "pydantic" in REQUIRED_PACKAGES