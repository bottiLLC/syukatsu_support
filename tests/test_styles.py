"""
Unit tests for UI Styles (src/ui/styles.py).
Ensures that essential style constants are defined and valid.
"""

from src.ui.styles import UI_COLORS, UI_FONTS, WINDOW_SIZE

def test_window_size_format():
    """Verify WINDOW_SIZE string format (WxH)."""
    assert isinstance(WINDOW_SIZE, str)
    parts = WINDOW_SIZE.split("x")
    assert len(parts) == 2
    assert parts[0].isdigit()
    assert parts[1].isdigit()

def test_ui_fonts_integrity():
    """Verify that required font definitions exist."""
    required_keys = ["BOLD", "TITLE", "MONO", "NORMAL", "STATUS"]
    for key in required_keys:
        assert key in UI_FONTS
        font_def = UI_FONTS[key]
        # Font def is tuple (Family, Size) or (Family, Size, Style)
        assert isinstance(font_def, tuple)
        assert len(font_def) >= 2
        assert isinstance(font_def[0], str) # Family
        assert isinstance(font_def[1], int) # Size

def test_ui_colors_integrity():
    """Verify that required color keys exist."""
    required_keys = ["TITLE", "USER_BG", "AI_FG", "ERROR_FG"]
    for key in required_keys:
        assert key in UI_COLORS
        color = UI_COLORS[key]
        assert isinstance(color, str)
        # Basic check for hex or named color
        assert color.startswith("#") or color.isalpha()