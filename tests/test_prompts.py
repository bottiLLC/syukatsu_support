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

import pytest

from src.core.prompts import MODE_ENTRY_SHEET, MODE_FINANCIAL, MODE_HUMAN_CAPITAL, PromptManager
from src.models import UserConfig


def test_prompts_structure() -> None:
    """[構造] 本番の system_prompts.json が生成する辞書が空ではないことを検証します。"""
    manager = PromptManager()
    prompts = manager.prompts
    assert isinstance(prompts, dict), "prompts must be a dict"
    assert len(prompts) > 0, "prompts cannot be empty (Ensure system_prompts.json exists in root)"


@pytest.mark.parametrize("required_key", [MODE_FINANCIAL, MODE_HUMAN_CAPITAL, MODE_ENTRY_SHEET])
def test_prompts_keys_exist(required_key: str) -> None:
    """[整合性] 必須の分析モードがキーとして存在することを検証します。"""
    manager = PromptManager()
    assert required_key in manager.prompts, f"Missing required key in JSON: {required_key}"


@pytest.mark.parametrize(
    "mode, expected_keywords",
    [
        (MODE_FINANCIAL, ["表の顔", "裏の顔", "キャッシュ・フロー"]),
        (MODE_HUMAN_CAPITAL, ["男女間賃金格差", "表の顔", "離職率"]),
        (MODE_ENTRY_SHEET, ["志望動機", "泥臭い課題", "キラーワード"]),
    ],
)
def test_prompts_content_integrity(mode: str, expected_keywords: list[str]) -> None:
    """[コンテンツ] プロンプトの内容が有効な文字列であり重要なドメインタームが含まれていることを検証します。"""
    manager = PromptManager()
    prompt_text = manager.get_prompt(mode)

    # 1. Type check
    assert isinstance(prompt_text, str), f"Prompt for {mode} must be a string"

    # 2. Not empty
    assert prompt_text.strip() != "", f"Prompt for {mode} is empty"

    # 3. Reasonable length check
    assert len(prompt_text) > 100, f"Prompt for {mode} seems suspiciously short."

    # 4. Keyword check
    for keyword in expected_keywords:
        assert keyword in prompt_text, f"Prompt for {mode} is missing expected keyword: '{keyword}'"


def test_prompts_contain_required_sections() -> None:
    """[構造] プロンプトにAIのための構造的ヘッダーが含まれていることを検証します。"""
    manager = PromptManager()
    for mode, prompt_text in manager.prompts.items():
        if not prompt_text:
            continue
        # Allow either standard English markdown headers or Japanese headers (e.g. ガクチカ添削)
        has_english_headers = "### ROLE" in prompt_text and "### OBJECTIVE" in prompt_text
        has_japanese_headers = "# 命令" in prompt_text and "# 出力形式" in prompt_text
        assert has_english_headers or has_japanese_headers, f"{mode} missing required section headers"


def test_default_config_key_exists_in_prompts() -> None:
    """[統合] UserConfig のデフォルトプロンプトモードが定義内に存在することを検証します。"""
    # Instantiate default config
    config = UserConfig()
    default_mode = config.system_prompt_mode

    manager = PromptManager()
    assert default_mode in manager.prompts, f"Default config mode '{default_mode}' is not defined in manager"


def test_legacy_mode_mapping_backward_compatibility() -> None:
    """[互換性] 旧分析モード名でリクエストした場合も同一のプロンプトが取得できることを検証します。"""
    manager = PromptManager()
    # 旧キーでも新キーでも同一のプロンプトが引けること
    assert manager.get_prompt("有価証券報告書 -財務分析-") == manager.get_prompt(MODE_FINANCIAL)
    assert manager.get_prompt("有価証券報告書 -人的資本分析-") == manager.get_prompt(MODE_HUMAN_CAPITAL)
    assert len(manager.get_prompt("有価証券報告書 -財務分析-")) > 100
