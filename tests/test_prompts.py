import pytest
from src.core.prompts import SYSTEM_PROMPTS
from src.config.app_config import UserConfig

def test_prompts_structure():
    """
    [Structure] SYSTEM_PROMPTS must be a non-empty dictionary.
    """
    assert isinstance(SYSTEM_PROMPTS, dict), "SYSTEM_PROMPTS must be a dict"
    assert len(SYSTEM_PROMPTS) > 0, "SYSTEM_PROMPTS cannot be empty"

@pytest.mark.parametrize("required_key", [
    "Root Cause Analysis",
    "Fact Finding",
    "Brainstorming (Wall-E)"
])
def test_prompts_keys_exist(required_key):
    """
    [Integrity] Verify that essential diagnostic modes exist as keys.
    """
    assert required_key in SYSTEM_PROMPTS, f"Missing required key: {required_key}"

@pytest.mark.parametrize("mode, expected_keywords", [
    ("Root Cause Analysis", ["4M分析", "安全第一"]),
    ("Fact Finding", ["5W1H", "事実調査"]),
    ("Brainstorming (Wall-E)", ["悪魔の代弁者", "確証バイアス"]),
])
def test_prompts_content_integrity(mode, expected_keywords):
    """
    [Content] Verify prompt content is valid strings and contains key domain terms.
    """
    prompt_text = SYSTEM_PROMPTS.get(mode)
    
    # 1. Type check
    assert isinstance(prompt_text, str), f"Prompt for {mode} must be a string"
    
    # 2. Not empty
    assert prompt_text.strip() != "", f"Prompt for {mode} is empty"

    # 3. Reasonable length check (sanity check against accidental deletion)
    assert len(prompt_text) > 50, f"Prompt for {mode} seems suspiciously short."
    
    # 4. Keyword check
    for keyword in expected_keywords:
        assert keyword in prompt_text, (
            f"Prompt for {mode} is missing expected keyword: '{keyword}'"
        )

def test_root_cause_analysis_safety_tags():
    """
    [Safety] Root Cause Analysis prompt must contain safety protocol tags.
    This is critical for AI safety behaviors.
    """
    prompt_text = SYSTEM_PROMPTS.get("Root Cause Analysis", "")
    
    required_tags = [
        "<safety_protocol", 
        "</safety_protocol>", 
        "<diagnostic_framework>"
    ]
    
    for tag in required_tags:
        assert tag in prompt_text, f"Missing safety tag '{tag}' in Root Cause Analysis prompt."

def test_default_config_key_exists_in_prompts():
    """
    [Integration] Verify that the default prompt mode in UserConfig 
    actually exists in the definitions.
    """
    # Instantiate default config
    config = UserConfig()
    default_mode = config.system_prompt_mode
    
    assert default_mode in SYSTEM_PROMPTS, (
        f"Default config mode '{default_mode}' is not defined in prompts.py"
    )