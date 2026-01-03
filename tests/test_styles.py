import pytest
import re
from src.ui.styles import WINDOW_SIZE, UI_FONTS, UI_COLORS

class TestUIStyles:

    def test_window_size_format(self):
        """[Integrity] Verify WINDOW_SIZE is a valid Tkinter geometry string (e.g., '1400x900')."""
        assert isinstance(WINDOW_SIZE, str)
        # Regex for WidthxHeight
        match = re.match(r"^\d+x\d+$", WINDOW_SIZE)
        assert match is not None, f"Invalid WINDOW_SIZE format: {WINDOW_SIZE}"
        
        width, height = map(int, WINDOW_SIZE.split("x"))
        assert width > 0
        assert height > 0

    def test_ui_fonts_structure(self):
        """[Integrity] Verify UI_FONTS dictionary structure and content."""
        assert isinstance(UI_FONTS, dict)
        
        required_keys = [
            "BOLD", "TITLE", "MONO", "NORMAL", "NORMAL_BOLD",
            "SMALL_MONO", "SMALL_BOLD", "STATUS", "STATUS_MONO"
        ]
        
        for key in required_keys:
            assert key in UI_FONTS, f"Missing font key: {key}"
            font_def = UI_FONTS[key]
            
            # Check tuple structure: (Family, Size) or (Family, Size, Style)
            assert isinstance(font_def, tuple)
            assert 2 <= len(font_def) <= 3
            
            # Check types
            assert isinstance(font_def[0], str) # Family
            assert isinstance(font_def[1], int) # Size
            if len(font_def) == 3:
                assert isinstance(font_def[2], str) # Style

    def test_ui_colors_structure(self):
        """[Integrity] Verify UI_COLORS dictionary structure and valid color values."""
        assert isinstance(UI_COLORS, dict)
        
        required_keys = [
            "TITLE", "USER_BG", "USER_FG", "AI_FG", 
            "ERROR_FG", "ID_FG", "LABEL_FG"
        ]
        
        hex_pattern = re.compile(r"^#(?:[0-9a-fA-F]{3}){1,2}$")
        
        for key in required_keys:
            assert key in UI_COLORS, f"Missing color key: {key}"
            color_val = UI_COLORS[key]
            
            assert isinstance(color_val, str)
            # Should be a hex code or a standard color name (simple check)
            is_hex = bool(hex_pattern.match(color_val))
            is_name = color_val.isalpha() # e.g. "red", "blue"
            
            assert is_hex or is_name, f"Invalid color format for {key}: {color_val}"