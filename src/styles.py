# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

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