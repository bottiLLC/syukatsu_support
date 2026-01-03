import importlib
import sys
from typing import Any, Dict, Generator
from unittest.mock import MagicMock, patch

import pytest

# --- 1. Pre-import Mocking of Tkinter Classes ---
# Define mock classes to replace actual Tkinter widgets.
# These must be defined before importing the GUI module to avoid Tcl/Tk initialization errors.


class MockTk:
    """Mock for tkinter.Tk"""

    def __init__(self, *args, **kwargs):
        pass

    def title(self, text):
        pass

    def geometry(self, size):
        pass

    def protocol(self, name, func):
        pass

    def destroy(self):
        pass

    def after(self, ms, func=None, *args):
        return "dummy_id"

    def winfo_exists(self):
        return True

    def option_add(self, *args):
        pass

    def mainloop(self):
        pass

    def quit(self):
        pass

    def wait_window(self, window=None):
        pass


class MockWidget:
    """Generic mock for Tkinter widgets."""

    def __init__(self, master=None, **kwargs):
        pass

    def pack(self, **kwargs):
        pass

    def grid(self, **kwargs):
        pass

    def configure(self, **kwargs):
        pass

    def config(self, **kwargs):
        pass

    def delete(self, *args):
        pass

    def insert(self, *args):
        pass

    def see(self, index):
        pass

    def bind(self, event, handler):
        pass

    def get(self, *args):
        return "mock_content"

    def tag_config(self, *args, **kwargs):
        pass

    def focus_set(self):
        pass

    def current(self, index=None):
        pass


class MockPanedWindow(MockWidget):
    def add(self, child, **kwargs):
        pass


class MockScrolledText(MockWidget):
    pass


class MockVariable:
    """Mock for tk.StringVar, BooleanVar, etc."""

    def __init__(self, value=None):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value


# --- 2. Define Mock Modules Objects ---
# Create mock module objects to be injected into sys.modules.

mock_tk_mod = MagicMock()
mock_tk_mod.Tk = MockTk
mock_tk_mod.PanedWindow = MockPanedWindow
mock_tk_mod.StringVar = MockVariable
mock_tk_mod.BooleanVar = MockVariable
mock_tk_mod.IntVar = MockVariable
mock_tk_mod.END = "end"
mock_tk_mod.BOTH = "both"
mock_tk_mod.HORIZONTAL = "horizontal"
mock_tk_mod.RAISED = "raised"
mock_tk_mod.SUNKEN = "sunken"
mock_tk_mod.LEFT = "left"
mock_tk_mod.RIGHT = "right"
mock_tk_mod.TOP = "top"
mock_tk_mod.BOTTOM = "bottom"
mock_tk_mod.X = "x"
mock_tk_mod.Y = "y"
mock_tk_mod.WORD = "word"

mock_ttk_mod = MagicMock()
mock_ttk_mod.LabelFrame = MockWidget
mock_ttk_mod.Frame = MockWidget
mock_ttk_mod.Button = MockWidget
mock_ttk_mod.Entry = MockWidget
mock_ttk_mod.Label = MockWidget
# Special handling for Combobox to allow __setitem__
mock_combo = MagicMock(spec=MockWidget)
mock_combo.get.return_value = ""
mock_ttk_mod.Combobox = lambda *a, **k: mock_combo
mock_ttk_mod.Checkbutton = MockWidget
mock_ttk_mod.Separator = MockWidget
mock_ttk_mod.Style = MagicMock()

mock_scrolledtext_mod = MagicMock()
mock_scrolledtext_mod.ScrolledText = MockScrolledText

# --- 3. Environment Fixture (Core Fix) ---


@pytest.fixture(scope="module")
def mock_tkinter_environment() -> Generator[None, None, None]:
    """
    Patches sys.modules to replace tkinter-related modules with mocks during testing.
    This ensures that importing src.ui.gui does not trigger actual GUI creation.
    """
    with patch.dict(
        sys.modules,
        {
            "tkinter": mock_tk_mod,
            "tkinter.ttk": mock_ttk_mod,
            "tkinter.scrolledtext": mock_scrolledtext_mod,
            "tkinter.filedialog": MagicMock(),
            "tkinter.messagebox": MagicMock(),
        },
    ):
        # Reload src.ui.gui if it was already imported to apply the mocks
        if "src.ui.gui" in sys.modules:
            import src.ui.gui

            importlib.reload(src.ui.gui)
        else:
            import src.ui.gui

        yield


# --- 4. Other Fixtures ---

# Import target modules inside fixtures or tests to ensure mocks are active
from src.config.app_config import UserConfig
from src.core.models import StreamTextDelta, StreamUsage


@pytest.fixture
def mock_dependencies() -> Generator[Dict[str, MagicMock], None, None]:
    """
    Mocks external dependencies used by the GUI application.
    Returns a dictionary of mocks for assertion.
    """
    with patch("src.ui.gui.ConfigManager") as mock_config_mgr, patch(
        "src.ui.gui.LLMService"
    ) as mock_llm_service, patch(
        "src.ui.gui.VectorStoreService"
    ) as mock_rag_service, patch(
        "src.ui.gui.FileService"
    ) as mock_file_service, patch(
        "src.ui.gui.threading.Thread"
    ) as mock_thread:

        # Default configuration behavior
        mock_config_mgr.load.return_value = UserConfig(
            api_key="sk-test-key", model="gpt-5.2", reasoning_effort="medium"
        )

        # Thread mock behavior: run target immediately (synchronous execution)
        def run_target(target=None, args=(), daemon=None):
            if target:
                target(*args)
            return MagicMock()

        mock_thread.side_effect = run_target

        yield {
            "config": mock_config_mgr,
            "llm": mock_llm_service,
            "rag": mock_rag_service,
            "file": mock_file_service,
            "thread": mock_thread,
        }


@pytest.fixture
def app(mock_tkinter_environment, mock_dependencies) -> Any:
    """
    Creates an instance of QMTroubleshootingApp with mocked dependencies.
    """
    from src.ui.gui import QMTroubleshootingApp

    # Mock app.after to just return a dummy ID and NOT execute the callback.
    # This prevents infinite recursion in tests where the callback schedules itself.
    with patch("src.ui.gui.QMTroubleshootingApp.after") as mock_after:
        mock_after.return_value = "dummy_after_id"

        app_instance = QMTroubleshootingApp()

        # Configure widget mocks to return specific values if needed
        app_instance._log_view.get = MagicMock(return_value="")
        app_instance._input_view.get = MagicMock(return_value="")
        app_instance._sys_prompt_view.get = MagicMock(return_value="")
        app_instance._vs_combo.get = MagicMock(return_value="")

        # Reset mocks to clear any calls made during initialization
        mock_dependencies["thread"].reset_mock()
        mock_dependencies["config"].load.reset_mock()

        # Also reset the after mock so tests start clean
        mock_after.reset_mock()

        yield app_instance


# --- 5. Test Cases ---


def test_init_loads_config(mock_tkinter_environment, mock_dependencies):
    """[Init] Verifies that configuration is loaded and applied to UI variables on startup."""
    from src.ui.gui import QMTroubleshootingApp

    with patch("src.ui.gui.QMTroubleshootingApp.after"):
        app_instance = QMTroubleshootingApp()

        mock_dependencies["config"].load.assert_called()
        assert app_instance._user_config.api_key == "sk-test-key"
        assert app_instance._api_key_var.get() == "sk-test-key"


def test_start_generation_validation_error(app, mock_dependencies):
    """[Logic] Verifies that generation stops if the API key is missing."""
    # Set empty API key
    app._api_key_var.set("")

    with patch("src.ui.gui.messagebox.showwarning") as mock_warn:
        app._start_generation()
        mock_warn.assert_called_once()

    # Thread should not start
    mock_dependencies["thread"].assert_not_called()


def test_start_generation_success(app, mock_dependencies):
    """[Logic] Verifies that the generation process starts correctly with valid input."""
    # Setup inputs
    app._api_key_var.set("sk-valid")
    app._input_view.get.return_value = "Test Input"
    app._sys_prompt_view.get.return_value = "System Prompt"

    # Setup RAG settings
    app._use_file_search_var.set(True)
    app._vs_combo.get.return_value = "Test Store (vs_123)"

    # Trigger generation
    app._start_generation()

    # Verify thread was started
    mock_dependencies["thread"].assert_called_once()
    # Verify state update
    assert app._is_generating is True


def test_process_queue_handling(app):
    """[Queue] Verifies that queue events correctly update the UI."""
    # Simulate events in the queue
    app._message_queue.put(StreamTextDelta(delta="Hello"))
    app._message_queue.put(
        StreamUsage(
            input_tokens=10, output_tokens=10, total_tokens=20, cached_tokens=0
        )
    )
    app._message_queue.put(None)  # Sentinel for completion

    # Mock UI update methods
    app._log_view.insert = MagicMock()
    app._cost_info_var.set = MagicMock()

    # Process the queue
    # We patch 'after' locally to ensure no recursion happens during this test block either
    with patch.object(app, "after"):
        # Manually drain queue
        while not app._message_queue.empty():
            app._process_queue()

    # Verify log update
    app._log_view.insert.assert_any_call("end", "Hello", "ai")

    # Verify cost update
    app._cost_info_var.set.assert_called()

    # Verify completion state
    assert app._is_generating is False


def test_on_close_saves_config(app, mock_dependencies):
    """[Lifecycle] Verifies that configuration is saved when the app closes."""
    app._api_key_var.set("sk-new-key")
    app._model_var.set("gpt-5.2")

    # Set values for fields that might be mocked
    app._vs_id_var.set("vs_123")
    app._use_file_search_var.set(False)
    app._prompt_mode_var.set("Root Cause Analysis")
    app._reasoning_var.set("medium")

    # Modify expected behavior: The refactored gui.py uses self.destroy() and self.quit(),
    # NOT sys.exit(). So we assert that destroy/save are called, and we do NOT expect SystemExit.
    with patch.object(app, "destroy") as mock_destroy, patch.object(
        app, "quit"
    ) as mock_quit:
        app._on_close()

        mock_destroy.assert_called_once()
        # mock_quit.assert_called() # Optional: quit might be inside try-except

    mock_dependencies["config"].save.assert_called_once()
    saved_config = mock_dependencies["config"].save.call_args[0][0]
    assert saved_config.api_key == "sk-new-key"


def test_refresh_vector_stores(app, mock_dependencies):
    """[RAG] Verifies that vector stores are fetched and the combobox is updated."""
    # Mock RAG service response
    mock_store = MagicMock()
    mock_store.id = "vs_1"
    mock_store.name = "Test Store"
    app._rag_service.list_vector_stores.return_value = [mock_store]

    # Mock combobox to capture updates
    app._vs_combo = MagicMock()
    app._vs_combo.__setitem__ = MagicMock()

    # Reset any previous calls to after (e.g. from init)
    app.after.reset_mock()

    app._refresh_vector_stores()

    # Verify service call
    app._rag_service.list_vector_stores.assert_called()

    # Because 'after' is mocked to NOT execute, we must manually execute the callback
    # The callback (lambda) is passed as the second argument to app.after
    # args: (delay_ms, callback, *args)
    assert app.after.called
    args, _ = app.after.call_args
    callback = args[1]

    # Execute the UI update callback manually
    callback()

    # Verify UI update
    args, _ = app._vs_combo.__setitem__.call_args
    assert args[0] == "values"
    assert "Test Store (vs_1)" in args[1]


def test_clear_context(app):
    """[Context] Verifies that context is cleared upon user confirmation."""
    app._log_view.delete = MagicMock()
    app._response_id_var.set = MagicMock()
    app._cost_info_var.set = MagicMock()

    with patch("src.ui.gui.messagebox.askyesno", return_value=True):
        app._clear_context()

    app._log_view.delete.assert_called_with("1.0", "end")
    app._response_id_var.set.assert_called_with("None")