import pytest
from unittest.mock import patch, MagicMock
from src.config.dependencies import check_dependencies

def test_repro():
    def mock_import_module_side_effect(name, *args, **kwargs):
        if name == "tenacity":
            raise ImportError("No module named 'tenacity'")
        return MagicMock()

    with patch("src.config.dependencies.importlib.import_module", side_effect=mock_import_module_side_effect):
        with patch("src.config.dependencies._show_error_dialog") as mock_show_error:
            with patch("src.config.dependencies.logger.critical") as mock_logger_critical:
                with pytest.raises(SystemExit) as excinfo:
                    check_dependencies()
                print("Mock was called:", mock_show_error.called)
                assert mock_show_error.call_count == 1
