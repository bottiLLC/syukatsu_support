import sys
import logging
import pytest
from unittest.mock import patch, MagicMock

# Target import
from src.config.dependencies import check_dependencies

# --- Fixtures ---

@pytest.fixture
def mock_gui():
    """
    Mocks the GUI components (tk, messagebox) to prevent actual window creation.
    Returns a dictionary of mocks for verification.
    """
    with patch("src.config.dependencies.tk") as mock_tk, \
         patch("src.config.dependencies.messagebox") as mock_msgbox:
        
        # Mock the root window instance
        mock_root = MagicMock()
        mock_tk.Tk.return_value = mock_root
        
        yield {
            "tk": mock_tk,
            "root": mock_root,
            "messagebox": mock_msgbox
        }

@pytest.fixture
def mock_logger():
    """Mocks the module logger."""
    with patch("src.config.dependencies.logger") as mock_log:
        yield mock_log

# --- Test Cases ---

def test_check_dependencies_success(mock_gui, mock_logger):
    """
    [Success] Verify that the function completes without error or exit
    when all dependencies are present.
    """
    # Assuming the test environment actually has these installed (or we assume standard behavior).
    # If we wanted to be strictly hermetic, we could mock __import__, but
    # allowing standard imports here verifies the test env is sane too.
    try:
        check_dependencies()
    except SystemExit:
        pytest.fail("check_dependencies raised SystemExit unexpectedly on success path.")

    # Verify NO error interactions occurred
    mock_logger.critical.assert_not_called()
    mock_gui["messagebox"].showerror.assert_not_called()
    mock_gui["tk"].Tk.assert_not_called()


@pytest.mark.parametrize("missing_pkg", ["openai", "pydantic", "httpx", "cryptography"])
def test_check_dependencies_missing_package(mock_gui, mock_logger, missing_pkg):
    """
    [Failure] Verify proper handling when a specific required package is missing.
    Should Log Critical -> Show Error Box -> Sys Exit.
    """
    # Save the original import function
    original_import = __import__

    def side_effect_import(name, *args, **kwargs):
        """Simulate ImportError only for the target package."""
        if name == missing_pkg:
            raise ImportError(f"No module named '{missing_pkg}'")
        return original_import(name, *args, **kwargs)

    # We patch builtins.__import__ to simulate the missing library
    with patch("builtins.__import__", side_effect=side_effect_import):
        # The function calls sys.exit(1), so we expect that exception
        with pytest.raises(SystemExit) as excinfo:
            check_dependencies()
        
        # 1. Check Exit Code
        assert excinfo.value.code == 1

        # 2. Check Logging
        mock_logger.critical.assert_called_once()
        log_msg = mock_logger.critical.call_args[0][0]
        assert f"Missing dependencies: {missing_pkg}" in log_msg

        # 3. Check GUI Error Box
        mock_gui["messagebox"].showerror.assert_called_once()
        args, _ = mock_gui["messagebox"].showerror.call_args
        assert args[0] == "Dependency Error" # Title
        assert missing_pkg in args[1] # Content

        # 4. Check Tkinter Lifecycle (Create hidden root -> Destroy)
        mock_gui["tk"].Tk.assert_called_once()
        mock_gui["root"].withdraw.assert_called_once()
        mock_gui["root"].destroy.assert_called_once()