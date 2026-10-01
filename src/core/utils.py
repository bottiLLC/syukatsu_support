"""ユーティリティおよびリソースパス解決モジュール。

PyInstaller実行時と通常開発時のパス解決、およびテキスト正規化関数を提供します。
"""

from __future__ import annotations

import json
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


def extract_markdown_content(raw_text: str | None) -> str:
    """JSON形式の構造化出力から markdown_content を抽出し、未完了のストリーミング断片も適切に復元します。

    Args:
        raw_text: モデルからの出力文字列 (JSONまたはプレーンテキスト)

    Returns:
        str: 抽出・復元されたMarkdownテキスト
    """
    if not raw_text:
        return ""

    trimmed = raw_text.strip()

    # 1. 完全なJSONのパース
    try:
        data = json.loads(trimmed)
        if isinstance(data, dict) and "markdown_content" in data:
            return str(data["markdown_content"])
    except Exception:
        pass

    # 2. ストリーミング中の部分文字列抽出
    match = re.search(r'"markdown_content"\s*:\s*"', raw_text)
    if match:
        content_part = raw_text[match.end() :]
        # 閉じ引用符（エスケープされていない二重引用符）を探索
        end_match = re.search(r'(?<!\\)(?:\\\\)*"', content_part)
        if end_match:
            # 閉じ引用符の手前までがコンテンツ
            content_part = content_part[: end_match.end() - 1]
        elif content_part.endswith("\\"):
            # ストリーミング途中でエスケープ途中の \ を一時除去
            content_part = content_part[:-1]

        # JSON文字列エスケープシーケンスのアンエスケープ
        return (
            content_part.replace(r"\"", '"')
            .replace(r"\n", "\n")
            .replace(r"\r", "\r")
            .replace(r"\t", "\t")
            .replace(r"\\", "\\")
        )

    return raw_text
