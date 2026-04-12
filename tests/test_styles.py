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