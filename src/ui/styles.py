"""
UI Styles configuration module.

This module defines constants for fonts, colors, and window settings
used across the GUI application to maintain consistent styling.
"""

from typing import Dict, Tuple, Union

# Type alias for Tkinter font definitions: (Family, Size) or (Family, Size, Style)
FontDef = Union[Tuple[str, int], Tuple[str, int, str]]

# Window Settings
WINDOW_SIZE: str = "1400x900"

# Font Configurations
UI_FONTS: Dict[str, FontDef] = {
    "BOLD": ("Segoe UI", 9, "bold"),
    "TITLE": ("Segoe UI", 11, "bold"),
    "MONO": ("Consolas", 9),
    "NORMAL": ("Segoe UI", 10),
    "NORMAL_BOLD": ("Segoe UI", 10, "bold"),
    "SMALL_MONO": ("Consolas", 8),
    "SMALL_BOLD": ("Consolas", 8, "bold"),
    "STATUS": ("Segoe UI", 9),
    "STATUS_MONO": ("Consolas", 9, "bold"),
}

# Color Palette
UI_COLORS: Dict[str, str] = {
    "TITLE": "#2c3e50",
    "USER_BG": "#ecf0f1",
    "USER_FG": "#2c3e50",
    "AI_FG": "#16a085",
    "ERROR_FG": "red",
    "ID_FG": "blue",
    "LABEL_FG": "gray",
}