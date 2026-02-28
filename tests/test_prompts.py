import pytest
from src.core.prompts import (
    SYSTEM_PROMPTS,
    MODE_FINANCIAL,
    MODE_HUMAN_CAPITAL,
    MODE_ENTRY_SHEET
)
from src.config.app_config import UserConfig

def test_prompts_structure():
    """
    [構造] SYSTEM_PROMPTS は空ではない辞書である必要があります。
    """
    assert isinstance(SYSTEM_PROMPTS, dict), "SYSTEM_PROMPTS must be a dict"
    assert len(SYSTEM_PROMPTS) > 0, "SYSTEM_PROMPTS cannot be empty"

@pytest.mark.parametrize("required_key", [
    MODE_FINANCIAL,
    MODE_HUMAN_CAPITAL,
    MODE_ENTRY_SHEET
])
def test_prompts_keys_exist(required_key):
    """
    [整合性] 必須の分析モードがキーとして存在することを検証します。
    """
    assert required_key in SYSTEM_PROMPTS, f"Missing required key: {required_key}"

@pytest.mark.parametrize("mode, expected_keywords", [
    (MODE_FINANCIAL, ["表の顔", "裏の顔", "投資対効果"]),
    (MODE_HUMAN_CAPITAL, ["男女の賃金の差異", "育児休業取得率", "離職率"]),
    (MODE_ENTRY_SHEET, ["志望動機", "解決したい悩み", "キラーワード"]),
])
def test_prompts_content_integrity(mode, expected_keywords):
    """
    [コンテンツ] プロンプトの内容が有効な文字列であり、重要なドメインタームが含まれているか検証します。
    """
    prompt_text = SYSTEM_PROMPTS.get(mode)
    
    # 1. Type check
    assert isinstance(prompt_text, str), f"Prompt for {mode} must be a string"
    
    # 2. Not empty
    assert prompt_text.strip() != "", f"Prompt for {mode} is empty"

    # 3. Reasonable length check
    assert len(prompt_text) > 100, f"Prompt for {mode} seems suspiciously short."
    
    # 4. Keyword check
    for keyword in expected_keywords:
        assert keyword in prompt_text, (
            f"Prompt for {mode} is missing expected keyword: '{keyword}'"
        )

def test_prompts_contain_required_sections():
    """
    [構造] プロンプトにはAIのための重要な構造的ヘッダーが含まれている必要があります。
    """
    for mode, prompt_text in SYSTEM_PROMPTS.items():
        if not prompt_text:
            continue
        assert "### ROLE" in prompt_text, f"{mode} missing ROLE section"
        assert "### OBJECTIVE" in prompt_text, f"{mode} missing OBJECTIVE section"
        assert "### OUTPUT CONSTRAINTS" in prompt_text, f"{mode} missing OUTPUT CONSTRAINTS section"

def test_default_config_key_exists_in_prompts():
    """
    [統合] UserConfig のデフォルトプロンプトモードが
    実際に定義内に存在することを検証します。
    """
    # Instantiate default config
    config = UserConfig()
    default_mode = config.system_prompt_mode
    
    assert default_mode in SYSTEM_PROMPTS, (
        f"Default config mode '{default_mode}' is not defined in prompts.py"
    )