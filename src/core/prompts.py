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
システムプロンプト定義モジュール。

このモジュールには、AIモデルが各種分析モードで使用する想定のシステム指示文と、
外部ファイル(system_prompts.json)から動的に読み込むための管理クラスが含まれています。
"""

import json
import structlog
from pathlib import Path
from typing import Dict, Final

log = structlog.get_logger()

# --- Analysis Mode Constants ---
MODE_FINANCIAL: Final[str] = "有価証券報告書 -財務分析-"
MODE_HUMAN_CAPITAL: Final[str] = "有価証券報告書 -人的資本分析-"
MODE_ENTRY_SHEET: Final[str] = "志望動機検討"
MODE_COMPETITOR_ANALYSIS: Final[str] = "有価証券報告書 -企業・経年比較分析-"
MODE_NO_PROMPT: Final[str] = "システムプロンプトなし"

class PromptManager:
    """
    外部の JSON ファイル (system_prompts.json) とプロンプトを同期・管理するクラス。
    """
    def __init__(self, filepath: str = "system_prompts.json"):
        # アプリ起動ディレクトリ(プロジェクトルート)に対する相対または絶対パス
        import sys
        import os
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.filepath = Path(base_path) / filepath
        self._prompts: Dict[str, str] = {}
        self._load()

    def _load(self):
        if self.filepath.exists():
            try:
                with self.filepath.open("r", encoding="utf-8") as f:
                    self._prompts = json.load(f)
                return
            except Exception as e:
                log.error("Failed to read prompt JSON", error=str(e))
        else:
            log.warning(f"Prompt JSON file not found: {self.filepath}")
            # 本番ファイルが存在しない場合の最小限のフェイルセーフ
            self._prompts = {
                MODE_FINANCIAL: "設定ファイルが見つかりません。",
                MODE_NO_PROMPT: ""
            }

    def save(self):
        try:
            with self.filepath.open("w", encoding="utf-8") as f:
                json.dump(self._prompts, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.error("Failed to save prompt JSON", error=str(e))

    def get_prompt(self, mode_name: str) -> str:
        return self._prompts.get(mode_name, "")

    def get_all_modes(self) -> list[str]:
        return list(self._prompts.keys())

    @property
    def prompts(self) -> dict:
            return self._prompts
