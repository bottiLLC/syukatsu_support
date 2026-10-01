"""システムプロンプト定義および管理モジュール。

外部JSONファイル (./data/system_prompts.json) と同期し、分析モード別のシステムプロンプトを管理します。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

import structlog

from src.core.utils import get_resource_path

log = structlog.get_logger()

# --- Analysis Mode Constants ---
MODE_FINANCIAL: Final[str] = "有価証券報告書 -財務分析-"
MODE_HUMAN_CAPITAL: Final[str] = "有価証券報告書 -人的資本分析-"
MODE_ENTRY_SHEET: Final[str] = "志望動機検討"
MODE_COMPETITOR_ANALYSIS: Final[str] = "有価証券報告書 -企業・経年比較分析-"
MODE_NO_PROMPT: Final[str] = "システムプロンプトなし"


class PromptManager:
    """外部 JSON ファイルとプロンプトを同期・管理するクラス。"""

    def __init__(self, filepath: str = "data/system_prompts.json") -> None:
        """PromptManager を初期化し、プロンプトデータをロードします。

        Args:
            filepath: システムプロンプト定義ファイルの相対パス
        """
        primary_path = get_resource_path(filepath)
        fallback_path = get_resource_path("system_prompts.json")

        if primary_path.exists():
            self.filepath: Path = primary_path
        elif fallback_path.exists():
            self.filepath = fallback_path
        else:
            self.filepath = primary_path

        self._prompts: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        """設定ファイルからプロンプトを読み込みます。"""
        if self.filepath.exists():
            try:
                with self.filepath.open("r", encoding="utf-8") as f:
                    self._prompts = json.load(f)
                return
            except (OSError, json.JSONDecodeError) as e:
                log.error("Failed to read prompt JSON", error=str(e), path=str(self.filepath))
        else:
            log.warning("Prompt JSON file not found", path=str(self.filepath))

        # 本番ファイルが存在しない場合の最小限のフェイルセーフ
        self._prompts = {
            MODE_FINANCIAL: "設定ファイルが見つかりません。",
            MODE_NO_PROMPT: "",
        }

    def save(self) -> None:
        """現在のプロンプトを設定ファイルに永続化します。"""
        try:
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            with self.filepath.open("w", encoding="utf-8") as f:
                json.dump(self._prompts, f, ensure_ascii=False, indent=2)
        except OSError as e:
            log.error("Failed to save prompt JSON", error=str(e), path=str(self.filepath))

    def get_prompt(self, mode_name: str) -> str:
        """指定された分析モードのプロンプト文字列を返します。

        Args:
            mode_name: 分析モードの名称

        Returns:
            str: 該当するシステムプロンプト文字列
        """
        return self._prompts.get(mode_name, "")

    def get_all_modes(self) -> list[str]:
        """利用可能な全分析モードのリストを返します。

        Returns:
            list[str]: 分析モード名のリスト
        """
        return list(self._prompts.keys())

    @property
    def prompts(self) -> dict[str, str]:
        """保持している全プロンプトの辞書を返します。"""
        return self._prompts
