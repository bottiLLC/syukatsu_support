"""
UIスタイル（src/ui/styles.py）のユニットテスト。
必須のスタイル定数が定義され、有効であることを保証します。
"""

from src.ui.styles import UI_COLORS, UI_FONTS, WINDOW_SIZE

def test_window_size_format():
    """WINDOW_SIZE文字列フォーマット（WxH）を検証します。"""
    assert isinstance(WINDOW_SIZE, str)
    parts = WINDOW_SIZE.split("x")
    assert len(parts) == 2
    assert parts[0].isdigit()
    assert parts[1].isdigit()

def test_ui_fonts_integrity():
    """必須のフォント定義が存在するか検証します。"""
    required_keys = ["BOLD", "TITLE", "MONO", "NORMAL", "STATUS"]
    for key in required_keys:
        assert key in UI_FONTS
        font_def = UI_FONTS[key]
        # フォント定義はタプル (Family, Size) または (Family, Size, Style)
        assert isinstance(font_def, tuple)
        assert len(font_def) >= 2
        assert isinstance(font_def[0], str) # Family
        assert isinstance(font_def[1], int) # Size

def test_ui_colors_integrity():
    """必須の色キーが存在するか検証します。"""
    required_keys = ["TITLE", "USER_BG", "AI_FG", "ERROR_FG"]
    for key in required_keys:
        assert key in UI_COLORS
        color = UI_COLORS[key]
        assert isinstance(color, str)
        # 16進数または指定された色の基本チェック
        assert color.startswith("#") or color.isalpha()