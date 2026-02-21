"""
Dependency verification module.

This module performs checks to ensure all required third-party libraries
are installed before the application attempts to import them.
"""

import importlib
import logging
import sys
import tkinter as tk
from tkinter import messagebox
from typing import List

# Setup logger
logger = logging.getLogger(__name__)

# List of required packages to verify at runtime
REQUIRED_PACKAGES = [
    "google.genai",
    "pydantic",
    "httpx",
    "cryptography",
    "dotenv",
    "tenacity",  # Added for retry logic resilience
]


def check_dependencies() -> None:
    """
    Verifies that all required third-party packages are installed.
    """
    # 【追加】PyInstallerでビルド済み(Frozen)の場合はチェックをスキップする
    if getattr(sys, 'frozen', False):
        logger.info("Running in frozen mode (PyInstaller). Skipping dependency check.")
        return

    missing_packages: List[str] = []

    for package in REQUIRED_PACKAGES:
        try:
            importlib.import_module(package)
        except ImportError:
            missing_packages.append(package)

    if missing_packages:
        _handle_missing_dependencies(missing_packages)


def _handle_missing_dependencies(missing_packages: List[str]) -> None:
    """
    Handles the scenario where dependencies are missing.

    Logs the error and displays a graphical alert before exiting the application.

    Args:
        missing_packages (List[str]): A list of package names that failed to import.
    """
    error_msg_log = f"Missing dependencies: {', '.join(missing_packages)}"
    logger.critical(error_msg_log)

    # User-facing message in Japanese
    display_msg = (
        "必要なライブラリが見つかりません。\n\n"
        "以下のコマンドを実行してインストールしてください:\n"
        f"pip install --upgrade {' '.join(missing_packages)}"
    )

    _show_error_dialog("Dependency Error", display_msg)
    sys.exit(1)


def _show_error_dialog(title: str, message: str) -> None:
    """
    Displays a Tkinter error message box safely.

    Creates a temporary root window if one does not exist to ensure
    the message box is visible.

    Args:
        title (str): The title of the error window.
        message (str): The error message content.
    """
    # Initialize a temporary root window to show the messagebox
    # since the main application window hasn't been created yet.
    try:
        # Check if root already exists to avoid TclError
        if not tk._default_root:
            root = tk.Tk()
            root.withdraw()  # Hide the main window
            should_destroy = True
        else:
            root = tk._default_root
            should_destroy = False
    except Exception:
        # Fallback
        root = tk.Tk()
        root.withdraw()
        should_destroy = True

    messagebox.showerror(title, message)

    # Ensure the root window is destroyed after the message box is closed
    if should_destroy:
        root.destroy()