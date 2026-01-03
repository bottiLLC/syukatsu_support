import sys
import pytest
from unittest.mock import patch, MagicMock

# Import the target module
# Note: We assume the project root is in PYTHONPATH
import main

class TestMainApplication:
    """
    Tests for the application entry point (main.py).
    """

    @pytest.fixture(autouse=True)
    def mock_dependencies(self):
        """
        Mock external dependencies for all tests to prevent side effects
        like logging to files or checking real packages.
        """
        with patch("main.setup_logging") as mock_log_setup, \
             patch("main.check_dependencies") as mock_check_deps, \
             patch("main.logger") as mock_logger:
            
            self.mock_log_setup = mock_log_setup
            self.mock_check_deps = mock_check_deps
            self.mock_logger = mock_logger
            yield

    def test_main_success_path(self):
        """
        [Happy Path] Verify correct startup sequence:
        Logging -> Dependencies -> GUI -> Mainloop
        """
        # Mock the GUI class imported *inside* main()
        # We patch 'src.ui.gui.QMTroubleshootingApp' because main.py imports it from there
        with patch("src.ui.gui.QMTroubleshootingApp") as MockApp:
            mock_app_instance = MockApp.return_value
            
            main.main()
            
            # 1. Logging setup
            self.mock_log_setup.assert_called_once()
            
            # 2. Dependency check
            self.mock_check_deps.assert_called_once()
            
            # 3. GUI Instantiation
            MockApp.assert_called_once()
            
            # 4. Mainloop start
            mock_app_instance.mainloop.assert_called_once()
            
            # No critical errors
            self.mock_logger.critical.assert_not_called()

    def test_main_startup_crash_handling(self):
        """
        [Error Path] Verify handling of exceptions during startup.
        Should log critical error, show messagebox, and exit(1).
        """
        # Simulate an error during GUI initialization
        error_msg = "Simulated Startup Crash"
        with patch("src.ui.gui.QMTroubleshootingApp", side_effect=RuntimeError(error_msg)):
            
            # Mock Tkinter components used in the exception block
            with patch("tkinter.Tk") as MockTk, \
                 patch("tkinter.messagebox.showerror") as mock_showerror, \
                 patch("tkinter._default_root", None): # Simulate no root existing
                
                # Expect sys.exit(1)
                with pytest.raises(SystemExit) as excinfo:
                    main.main()
                
                assert excinfo.value.code == 1
                
                # 1. Verify Logging
                self.mock_logger.critical.assert_called_once()
                args, kwargs = self.mock_logger.critical.call_args
                assert error_msg in str(args[0])
                assert kwargs.get('exc_info') is True
                
                # 2. Verify Fallback Root Creation (since _default_root was None)
                # It should create a Tk instance and withdraw (hide) it
                MockTk.assert_called_once()
                MockTk.return_value.withdraw.assert_called_once()
                
                # 3. Verify User Alert
                mock_showerror.assert_called_once()
                call_args = mock_showerror.call_args[0]
                assert "重大なエラー" in call_args[0]
                assert error_msg in call_args[1]

    def test_main_crash_with_existing_root(self):
        """
        [Error Path] Verify exception handling when a Tk root already exists.
        Should NOT create a new Tk instance, but still show error.
        """
        # Simulate error
        with patch("src.ui.gui.QMTroubleshootingApp", side_effect=ValueError("Config Error")):
             
             # Simulate existing root
             mock_existing_root = MagicMock()
             
             with patch("tkinter.Tk") as MockTk, \
                  patch("tkinter.messagebox.showerror") as mock_showerror, \
                  patch("tkinter._default_root", mock_existing_root):
                 
                 with pytest.raises(SystemExit):
                     main.main()
                 
                 # Should NOT create new root because one exists
                 MockTk.assert_not_called()
                 
                 # Should still show error
                 mock_showerror.assert_called()