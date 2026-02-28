"""
就活サポートアプリのUIスタイル設定モジュール。

このモジュールは、GUIアプリケーション全体で使用される一貫したスタイリングを維持するための
フォント、色、およびウィンドウ設定の定数を定義します。
"""

from typing import Dict, Tuple, Union

# Tkinterフォント定義の型エイリアス: (Family, Size) または (Family, Size, Style)
FontDef = Union[Tuple[str, int], Tuple[str, int, str]]

# ウィンドウ設定
WINDOW_SIZE: str = "1400x900"

# フォント設定
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

# カラーパレット
UI_COLORS: Dict[str, str] = {
    "TITLE": "#2c3e50",
    "USER_BG": "#ecf0f1",
    "USER_FG": "#2c3e50",
    "AI_FG": "#16a085",
    "ERROR_FG": "red",
    "ID_FG": "blue",
    "LABEL_FG": "gray",
}