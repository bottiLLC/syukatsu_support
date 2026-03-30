"""
就活サポートアプリのUIスタイル設定モジュール。

このモジュールは、GUIアプリケーション全体で使用される一貫したスタイリングを維持するための
フォント、色、およびウィンドウ設定の定数を定義します。
"""

from typing import Dict, Tuple, Union

# Tkinter等のため定義したフォントの型エイリアス（将来の拡張用）
FontDef = Union[Tuple[str, int], Tuple[str, int, str]]

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