# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

from src.core.utils import clean_citation_markers, get_resource_path


def test_clean_citation_markers():
    # 通常のテキスト
    text1 = "売上高は前年比15%増の1,000億円となりました。[P.45 【連結損益計算書】]"
    assert clean_citation_markers(text1) == text1

    # filecite タグが含まれるテキスト
    text2 = "売上高は〇〇億円です。[【連結損益計算書】] fileciteturn2file0"
    expected2 = "売上高は〇〇億円です。[【連結損益計算書】] "
    assert clean_citation_markers(text2) == expected2

    # 複数の filecite タグが含まれるテキスト
    text3 = "A社 filecite123 B社 fileciteturn5file1 C社"
    expected3 = "A社  B社  C社"
    assert clean_citation_markers(text3) == expected3

    # 空文字列や None
    assert clean_citation_markers("") == ""
    assert clean_citation_markers(None) is None


def test_get_resource_path():
    path = get_resource_path("system_prompts.json")
    assert path.name == "system_prompts.json"
