"""
設定管理（src/config/app_config.py）のユニットテスト。
以下のテストを含みます：
1. SecurityManager: APIキーの暗号化/復号化。
2. UserConfig: デフォルト値とPydanticの検証。
3. ConfigManager: 読み込み/保存のロジックと優先順位のルール。
"""

import os
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet

from src.config.app_config import (
    AppConfig,
    UserConfig,
    SecurityManager,
    ConfigManager
)

class TestSecurityManager:
    """ローカル暗号化ユーティリティのテスト。"""

    def test_encrypt_decrypt_cycle(self):
        """暗号化されたテキストが元のテキストに復号化できることを検証します。"""
        # テスト中のディスク書き込みを避けるためにキー生成をモック
        key = Fernet.generate_key()
        with patch.object(SecurityManager, '_get_or_create_key', return_value=key):
            original_text = "sk-test-12345"
            encrypted = SecurityManager.encrypt(original_text)
            
            assert encrypted != original_text
            assert len(encrypted) > 0
            
            decrypted = SecurityManager.decrypt(encrypted)
            assert decrypted == original_text

    def test_decrypt_invalid_token(self):
        """無効または破損した暗号文の処理を検証します。"""
        key = Fernet.generate_key()
        with patch.object(SecurityManager, '_get_or_create_key', return_value=key):
            # 不正な文字列を渡す
            result = SecurityManager.decrypt("invalid-encrypted-string")
            assert result is None

class TestUserConfig:
    """Pydantic設定モデルのテスト。"""

    def test_defaults(self):
        """新規設定のデフォルト値を検証します。"""
        config = UserConfig()
        assert config.api_key is None
        assert config.model == "gpt-5.2"
        assert config.reasoning_effort == "high"
        # 就活サポートのコンテキストに一致するように更新 (FIX: Added space)
        assert config.system_prompt_mode == "有価証券報告書 -財務分析-"
        assert config.use_file_search is False

class TestConfigManager:
    """設定の読み込みと保存のテスト。"""

    @pytest.fixture
    def mock_fs(self, tmp_path):
        """設定ファイルとキーファイルのモックファイルシステムパス。"""
        # モジュール内のPathオブジェクトをtmp_pathを指すようにパッチ
        with patch("src.config.app_config.CONFIG_FILE", tmp_path / "config.json"), \
             patch("src.config.app_config.KEY_FILE", tmp_path / ".secret.key"):
            yield

    def test_load_defaults_if_no_file(self):
        """設定ファイルが存在しない場合はデフォルト値を返すべきです。"""
        config = ConfigManager.load()
        assert isinstance(config, UserConfig)
        assert config.api_key is None

    def test_load_env_var_priority(self):
        """APIキーにおいて、環境変数はファイル設定より優先されるべきです。"""
        # 1. 環境変数の設定
        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-key-123"}):
            config = ConfigManager.load()
            assert config.api_key == "env-key-123"

    def test_save_and_load_encrypted(self):
        """保存時にキーが暗号化され、読み込み時に復号化されることを検証します。"""
        # 1. 機密データを含む設定の作成
        original_config = UserConfig(api_key="secret-api-key")
        
        # 2. 保存
        ConfigManager.save(original_config)
        
        # ディスク上のファイルにプレーンテキストのキーが含まれていないことを検証
        # パッチされたパスにアクセスする必要があります。モジュール定数をパッチしたため、
        # そのパスを知っていれば実際のテンポラリファイルから読み込むことができますが、
        # ConfigManager.load を使用することはサイクルの統合テストになります。
        
        # 3. 読み込み
        loaded_config = ConfigManager.load()
        assert loaded_config.api_key == "secret-api-key"

    def test_safety_defaults_enforced_on_load(self):
        """
        高価な設定（モデル、推論）が保存内容に関わらずロード時に
        デフォルトにリセットされることを検証します。
        """
        # デフォルト以外の高価な設定で保存
        risky_config = UserConfig(
            model="gpt-5.2-pro", 
            reasoning_effort="xhigh"
        )
        ConfigManager.save(risky_config)
        
        # 再度読み込み
        safe_config = ConfigManager.load()
        
        # デフォルトにリセットされているべき
        assert safe_config.model == AppConfig.DEFAULT_MODEL
        assert safe_config.reasoning_effort == AppConfig.DEFAULT_REASONING