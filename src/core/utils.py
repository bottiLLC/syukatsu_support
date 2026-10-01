"""ユーティリティおよびリソースパス解決モジュール。

PyInstaller実行時と通常開発時のパス解決、およびテキスト正規化関数を提供します。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Final

# OpenAI Vector Store (file_search) および Web検索の内部引用マーカー正規表現
# 例: turn1file2, fileciteturn2file0, 【turn1file2】, [turn1file2], 【4:0†source】
# 通常の有報引用形式（[P.45 【連結損益計算書】] 等）は安全に保持
_CITATION_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?:【[^】]*?(?:turn\d+|source|filecite)[^】]*?】"
    r"|\[(?:turn\d+file\d+|turn\d+search\d+|filecite[a-zA-Z0-9]*)\]"
    r"|filecite[a-zA-Z0-9]*"
    r"|turn\d+(?:file|search)\d+)"
)


def get_resource_path(relative_path: str | Path) -> Path:
    """PyInstaller実行時 (sys._MEIPASS) と通常開発時のリソース絶対パスを取得します。

    Args:
        relative_path: プロジェクトルートからの相対パス (例: "system_prompts.json")

    Returns:
        Path: 解決された絶対パス
    """
    base_path = Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS") else Path(__file__).resolve().parent.parent.parent

    return (base_path / relative_path).resolve()


def clean_citation_markers(text: str | None) -> str | None:
    """LLMが内部的に出力した引用タグ（turn1file2, filecite 等）を正規表現で削除します。

    Args:
        text: 削除対象のテキスト (None許容)

    Returns:
        str | None: 内部引用タグが除去されたテキスト
    """
    if text is None:
        return None
    if not text:
        return ""
    return _CITATION_PATTERN.sub("", text)
