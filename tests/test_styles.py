"""
UIスタイル（src/ui/styles.py）のユニットテスト。
必須のスタイル定数が定義され、有効であることを保証します。
"""

from src.styles import UI_COLORS

def test_ui_colors_integrity():
    """必須の色キーが存在するか検証します。"""
    required_keys = ["TITLE", "USER_BG", "AI_FG", "ERROR_FG"]
    for key in required_keys:
        assert key in UI_COLORS
        color = UI_COLORS[key]
        assert isinstance(color, str)
        # 16進数または指定された色の基本チェック
        assert color.startswith("#") or color.isalpha()