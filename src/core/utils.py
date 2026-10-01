"""ユーティリティおよびリソースパス解決モジュール。

PyInstaller実行時と通常開発時のパス解決、およびテキスト正規化関数を提供します。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def get_resource_path(relative_path: str | Path) -> Path:
    """PyInstaller実行時 (sys._MEIPASS) と通常開発時のリソース絶対パスを取得します。

    Args:
        relative_path: プロジェクトルートからの相対パス (例: "system_prompts.json")

    Returns:
        Path: 解決された絶対パス
    """
    base_path = Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS") else Path(__file__).resolve().parent.parent.parent

    return (base_path / relative_path).resolve()


def clean_citation_markers(text: str) -> str:
    """LLMが内部的に出力した filecite タグを正規表現で削除します。

    Args:
        text: 削除対象のテキスト

    Returns:
        str: 内部タグが削除されたテキスト
    """
    if not text:
        return text
    return re.sub(r"filecite[a-zA-Z0-9]*", "", text)
