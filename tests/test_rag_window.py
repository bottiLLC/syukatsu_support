"""
Unit tests for the RAG Management Window GUI.
Uses strict module patching to prevent ANY Tkinter code from executing.
"""

import sys
import pytest
from unittest.mock import MagicMock, patch

# --- Helper to force-reload module with mocks ---
def _import_isolated_rag_window():
    """
    Imports src.ui.rag_window with tkinter mocked out globally.
    Ensures the class inherits from a dummy class, avoiding MagicMock init issues.
    """
    # 1. Create Mocks for tkinter
    mock_tk = MagicMock()
    
    # Define a plain dummy class for Toplevel
    class DummyToplevel:
        def __init__(self, master=None, **kwargs):
            self.tk = MagicMock()
            self._w = "dummy_window"
            self.master = master
            # Mock common Toplevel methods
            self.title = MagicMock()
            self.geometry = MagicMock()
            self.transient = MagicMock()
            self.grab_set = MagicMock()
            self.destroy = MagicMock()
            self.wait_window = MagicMock()
            self.config = MagicMock()
            self.after = MagicMock()
            self.update_idletasks = MagicMock()

    mock_tk.Toplevel = DummyToplevel
    
    # Create mocks for submodules
    mock_ttk = MagicMock()
    mock_messagebox = MagicMock() # Explicit mock for messagebox
    
    # [IMPORTANT] Link the sub-mock to the parent mock
    # This ensures 'from tkinter import messagebox' gets the same object 
    # as 'import tkinter.messagebox'
    mock_tk.messagebox = mock_messagebox
    
    # 2. Patch sys.modules to inject our mocks BEFORE import
    with patch.dict(sys.modules, {
        "tkinter": mock_tk,
        "tkinter.ttk": mock_ttk,
        "tkinter.messagebox": mock_messagebox,
        "tkinter.simpledialog": MagicMock(),
        "tkinter.filedialog": MagicMock(),
        "src.ui.rag_window.tk": mock_tk,   
        "src.ui.rag_window.ttk": mock_ttk,
    }):
        # 3. Force reload if already loaded
        if "src.ui.rag_window" in sys.modules:
            del sys.modules["src.ui.rag_window"]
            
        from src.ui.rag_window import RAGManagementWindow
        # Return the class and the specific mocks we want to assert on
        return RAGManagementWindow, mock_tk, mock_ttk, mock_messagebox

class TestRAGManagementWindow:
    
    @pytest.fixture
    def mock_services(self):
        """Mock backend services."""
        return MagicMock(), MagicMock()

    @pytest.fixture
    def window_setup(self, mock_services):
        """
        Fixture that returns:
        (window_instance, rag_service_mock, file_service_mock, messagebox_mock)
        """
        rag_service, file_service = mock_services
        
        # Import the class securely
        RAGWindowCls, _, mock_ttk, mock_msgbox = _import_isolated_rag_window()
        
        # Patch threading to run synchronously
        with patch("threading.Thread") as MockThread:
            # Execute target immediately
            def side_effect_run(target, daemon=True):
                target() 
                return MagicMock()
            MockThread.side_effect = side_effect_run
            MockThread.return_value.start.side_effect = lambda: None

            mock_parent = MagicMock()
            
            # Instantiate
            win = RAGWindowCls(mock_parent, rag_service, file_service)
            
            # Manually attach UI mocks / ensure attributes exist
            if not hasattr(win, '_store_tree'): win._store_tree = MagicMock()
            if not hasattr(win, '_file_tree'): win._file_tree = MagicMock()
            
            # Setup specific return values for the mock widgets
            win._store_tree.selection.return_value = []
            
            # Ensure methods expected by logic exist on the instance
            win.after = MagicMock()
            win.update_idletasks = MagicMock()
            win.config = MagicMock()
            win._rename_btn = MagicMock()
            win._upload_btn = MagicMock()
            
            yield win, rag_service, file_service, mock_msgbox
            
            # Cleanup
            try:
                win.destroy()
            except:
                pass

    def test_initial_load(self, window_setup):
        """Verify that stores are loaded on init."""
        win, rag_service, _, _ = window_setup
        
        # Setup mock return
        mock_store = MagicMock()
        mock_store.id = "vs_1"
        mock_store.name = "Test Store"
        mock_store.status = "completed"
        mock_store.usage_bytes = 100
        mock_store.file_counts = MagicMock(total=5) 
        
        rag_service.list_vector_stores.return_value = [mock_store]
        
        # Manually trigger refresh logic
        win._refresh_stores_async()
        
        # Verify service called
        rag_service.list_vector_stores.assert_called()
        
        # Manually trigger UI update
        win._update_store_list([mock_store])
        
        # Verify treeview insert
        win._store_tree.insert.assert_called()
        
        # Check arguments passed to insert
        call_args = win._store_tree.insert.call_args
        # Expected call: insert("", "end", values=(...))
        # call_args[0] are positional args (" ", "end")
        # call_args[1] are kwargs {"values": (...)}
        
        # Verify kwargs content
        values = call_args[1].get('values') or call_args.kwargs.get('values')
        
        # If passed as positional (unlikely given the code but possible if mocked differently):
        if not values and len(call_args[0]) > 2:
            values = call_args[0][2]
            
        assert values is not None
        assert values[0] == "Test Store"
        assert values[1] == "vs_1"

    def test_selection_update_button_state(self, window_setup):
        """Verify that selecting a store enables buttons."""
        win, _, _, _ = window_setup
        
        # Simulate selection
        win._store_tree.selection.return_value = ["item_1"]
        win._store_tree.item.return_value = {
            "values": ["Test Store", "vs_id_123", "completed", "5", "100"]
        }
        
        # Call handler
        win._on_store_select(None)
        
        # Verify internal state
        assert win._current_store_id == "vs_id_123"
        
        # Verify buttons enabled
        win._rename_btn.config.assert_called_with(state="normal")
        win._upload_btn.config.assert_called_with(state="normal")

    def test_delete_store_safety_check(self, window_setup):
        """Verify that deleting a non-empty store shows warning."""
        win, rag_service, _, mock_msgbox = window_setup
        
        # Setup state
        win._current_store_id = "vs_populated"
        win._current_store_file_count = 5
        
        # Execute delete
        win._delete_store()
        
        # Should warn using the messagebox mock we injected
        mock_msgbox.showwarning.assert_called()
        assert "削除できません" in mock_msgbox.showwarning.call_args[0][0]
        
        # Should not call delete
        rag_service.delete_vector_store.assert_not_called()