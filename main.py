"""
Job Hunting Support Application Entry Point.

This module serves as the bootstrap script for the SyukatsuSupportApp.
It orchestrates logging setup, dependency verification, and GUI initialization.
"""

import logging
import sys
import tkinter as tk
from tkinter import messagebox

# Local imports
from src.config.dependencies import check_dependencies
from src.config.logging_config import setup_logging

# Initialize logger
logger = logging.getLogger(__name__)


def show_splash() -> tk.Tk:
    """Creates and displays a lightweight splash screen."""
    splash = tk.Tk()
    splash.overrideredirect(True)  # Remove window decorations
    splash.geometry("400x150")
    splash.eval('tk::PlaceWindow . center')
    
    # Basic styling
    frame = tk.Frame(splash, bg="white", highlightbackground="#007BFF", highlightthickness=2)
    frame.pack(expand=True, fill="both")
    
    label = tk.Label(
        frame, 
        text="就活サポートアプリ起動中...", 
        font=("Helvetica", 14, "bold"), 
        bg="white",
        fg="#333333"
    )
    label.pack(expand=True)
    
    # Force UI update to show immediately
    splash.update()
    return splash

def main() -> None:
    """
    Main execution routine.

    Orchestrates the application startup sequence:
    1. Shows lightweight splash screen.
    2. Configures logging.
    3. Checks for required dependencies.
    4. Launches the main GUI application.
    """
    # Show splash screen as fast as possible
    splash = show_splash()

    # 1. Setup Logging
    setup_logging()
    logger.info("Application starting...")

    # 2. Check Dependencies
    # Must be done before importing modules that use these dependencies
    check_dependencies()

    try:
        # 3. Launch GUI
        # Import inside main/try block to capture import errors if dependencies fail
        # pylint: disable=import-outside-toplevel
        from src.ui.gui import SyukatsuSupportApp

        logger.info("Initializing GUI...")
        app = SyukatsuSupportApp()
        
        # Destroy splash right before showing main window
        splash.destroy()
        
        app.mainloop()

    except Exception as e:
        logger.critical(f"Application failed to start: {e}", exc_info=True)

        # Fallback error reporting using a temporary Tk instance if the app crashed
        # before the main window could handle the error.
        try:
            # If Tkinter hasn't been initialized or was destroyed, ensure we have a root.
            # Accessing protected member _default_root to check state.
            # pylint: disable=protected-access
            if not tk._default_root:  # type: ignore
                tk.Tk().withdraw()
        except Exception:
            # Ignore errors during fallback mechanism to ensure the message box attempt proceeds
            pass

        messagebox.showerror(
            "重大なエラー",
            f"アプリケーションの起動中に予期せぬエラーが発生しました。\n\n{e}",
        )
        sys.exit(1)


if __name__ == "__main__":
    main()