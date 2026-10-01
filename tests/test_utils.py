# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""ユーティリティモジュールのユニットテスト。"""

from __future__ import annotations

from src.core.utils import clean_citation_markers, extract_markdown_content, get_resource_path


def test_clean_citation_markers() -> None:
    """テキストから内部引用タグ（turn1file2, filecite等）が正しく除去されることを検証します。"""
    # 通常のテキスト（正常な有報引用 [P.45 【連結損益計算書】] は保持）
    text1 = "売上高は前年比15%増の1,000億円となりました。[P.45 【連結損益計算書】]"
    assert clean_citation_markers(text1) == text1

    # filecite タグが含まれるテキスト
    text2 = "売上高は〇〇億円です。[【連結損益計算書】] fileciteturn2file0"
    expected2 = "売上高は〇〇億円です。[【連結損益計算書】] "
    assert clean_citation_markers(text2) == expected2

    # プレフィックスなしの turn1file2 が埋め込まれたテキスト
    text3 = "営業利益は大幅に増加しましたturn1file2。[P.12 【経営成績】]"
    expected3 = "営業利益は大幅に増加しました。[P.12 【経営成績】]"
    assert clean_citation_markers(text3) == expected3

    # 【turn1file2】 や [turn1file2] や 【4:0†source】 形式
    text4 = "当期純利益は改善しました【turn1file2】。キャッシュフローも健全です [turn0file1]【4:0†source】。"
    expected4 = "当期純利益は改善しました。キャッシュフローも健全です 。"
    assert clean_citation_markers(text4) == expected4

    # 複数の filecite タグが含まれるテキスト
    text5 = "A社 filecite123 B社 fileciteturn5file1 C社"
    expected5 = "A社  B社  C社"
    assert clean_citation_markers(text5) == expected5

    # 空文字列や None
    assert clean_citation_markers("") == ""
    assert clean_citation_markers(None) is None


def test_get_resource_path() -> None:
    """リソースファイル名から正しい絶対パスが解決されることを検証します。"""
    path = get_resource_path("system_prompts.json")
    assert path.name == "system_prompts.json"


def test_extract_markdown_content() -> None:
    """JSON形式の構造化出力から markdown_content が正しく抽出・復元されることを検証します。"""
    import json

    # 1. 完全なJSONオブジェクト
    full_json = json.dumps({"markdown_content": "# 財務分析\n\n- 売上高: 100億円\n**総評**"})
    assert extract_markdown_content(full_json) == "# 財務分析\n\n- 売上高: 100億円\n**総評**"

    # 2. ストリーミング中の不完全なJSONプレフィックス
    stream_chunk1 = '{"markdown_content": "# 財務分析\\n\\n- 売上'
    assert extract_markdown_content(stream_chunk1) == "# 財務分析\n\n- 売上"

    # 3. 閉じ中括弧付きのJSON文字列
    stream_chunk2 = '{"markdown_content": "本文テスト"}'
    assert extract_markdown_content(stream_chunk2) == "本文テスト"

    # 4. エスケープされた引用符およびストリーミング途中エスケープの処理
    stream_chunk3 = '{"markdown_content": "テキスト\\"と引用"}'
    assert extract_markdown_content(stream_chunk3) == 'テキスト"と引用'

    stream_chunk4 = '{"markdown_content": "テキスト\\'
    assert extract_markdown_content(stream_chunk4) == "テキスト"

    # 5. 通常のプレーンテキスト（非JSON）はそのまま返却
    plain_text = "通常のプレーンテキスト返答です。"
    assert extract_markdown_content(plain_text) == plain_text

    # 6. 空文字・Noneの安全処理
    assert extract_markdown_content("") == ""
    assert extract_markdown_content(None) == ""
