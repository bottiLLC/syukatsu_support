import json
import os
import pytest
from unittest.mock import MagicMock, patch, mock_open
from src.config.app_config import SecurityManager, ConfigManager, UserConfig, AppConfig

# --- SecurityManager Tests ---

@pytest.fixture
def mock_key_file():
    """Mocks the KEY_FILE Path object to prevent real file I/O."""
    with patch("src.config.app_config.KEY_FILE") as mock_path:
        # Default behavior: File exists and contains a valid Fernet key
        # We generate a real key for the tests to make Fernet happy
        from cryptography.fernet import Fernet
        real_key = Fernet.generate_key()
        mock_path.exists.return_value = True
        mock_path.read_bytes.return_value = real_key
        yield mock_path

def test_encrypt_decrypt_cycle(mock_key_file):
    """[Security] 正常系: 文字列の暗号化と復号化が正しく行われることを検証。"""
    plaintext = "sk-test-12345"
    
    encrypted = SecurityManager.encrypt(plaintext)
    assert encrypted != plaintext
    assert isinstance(encrypted, str)
    assert len(encrypted) > 0
    
    decrypted = SecurityManager.decrypt(encrypted)
    assert decrypted == plaintext

def test_key_generation_if_missing(mock_key_file):
    """[Security] 正常系: キーファイルが存在しない場合、新規生成して保存されるか検証。"""
    mock_key_file.exists.return_value = False
    
    # トリガー: encryptを呼ぶとキーロード/生成が走る
    SecurityManager.encrypt("test")
    
    # 検証
    assert mock_key_file.write_bytes.called

@patch("os.name", "posix")
def test_key_permissions_on_posix(mock_key_file):
    """[Security] 正常系: POSIX環境でキー生成時に chmod 600 が設定されるか検証。"""
    mock_key_file.exists.return_value = False
    
    SecurityManager.encrypt("test")
    
    mock_key_file.chmod.assert_called_with(0o600)

def test_decrypt_invalid_token(mock_key_file):
    """[Security] 異常系: 無効または破損したトークンの復号時に None が返されるか検証。"""
    result = SecurityManager.decrypt("invalid-token-string")
    assert result is None

def test_security_manager_file_io_error(mock_key_file):
    """[Security] 異常系: キーファイルの読み書きで IOError が発生した場合のハンドリング。"""
    # 読み込みエラー
    mock_key_file.exists.return_value = True
    mock_key_file.read_bytes.side_effect = IOError("Permission denied")
    
    # 修正: 実装(SecurityManager)は例外をログ出力して握りつぶし、空文字を返す仕様のため
    # pytest.raises(IOError) ではなく、戻り値が空文字であることを検証する
    result = SecurityManager.encrypt("test")
    assert result == ""

# --- ConfigManager Tests ---

@pytest.fixture
def mock_config_file():
    """Mocks the CONFIG_FILE Path object."""
    with patch("src.config.app_config.CONFIG_FILE") as mock_path:
        yield mock_path

def test_load_defaults_no_file(mock_config_file):
    """[Config] 正常系: 設定ファイルがない場合、デフォルト設定がロードされるか検証。"""
    mock_config_file.exists.return_value = False
    
    with patch.dict(os.environ, {}, clear=True):
        config = ConfigManager.load()
        
        assert isinstance(config, UserConfig)
        assert config.api_key is None
        assert config.model == "gpt-5.2"  # AppConfig.DEFAULT_MODEL
        assert config.reasoning_effort == "high" # AppConfig.DEFAULT_REASONING

def test_load_from_environment_variable(mock_config_file):
    """[Config] 正常系: 環境変数 OPENAI_API_KEY が優先されるか検証。"""
    mock_config_file.exists.return_value = False
    
    with patch.dict(os.environ, {"OPENAI_API_KEY": "env-key-123"}):
        config = ConfigManager.load()
        assert config.api_key == "env-key-123"

def test_save_config_security(mock_config_file, mock_key_file):
    """[Config] Security: APIキーが暗号化され、平文で保存されていないことを厳密に検証。"""
    config = UserConfig(
        api_key="secret-key-123",
        model="gpt-5.2",
        reasoning_effort="medium"
    )
    
    # mock_open を作成
    m_open = mock_open()
    # CONFIG_FILE.open() が呼ばれたときに m_open を返すように設定
    # builtins.open ではなく、Pathオブジェクトの open メソッドをモックする
    mock_config_file.open.side_effect = m_open
    
    ConfigManager.save(config)
    
    # 書き込み内容を取得
    write_args = m_open().write.call_args_list
    written_str = "".join(args[0] for args, _ in write_args)
    saved_json = json.loads(written_str)
    
    # 検証
    assert "api_key" not in saved_json, "平文のAPIキーがJSONに含まれています！"
    assert "encrypted_api_key" in saved_json
    assert saved_json["encrypted_api_key"] != "secret-key-123"
    
    # 暗号化された値を復号して一致確認
    decrypted = SecurityManager.decrypt(saved_json["encrypted_api_key"])
    assert decrypted == "secret-key-123"

def test_load_and_decrypt_config(mock_config_file, mock_key_file):
    """[Config] 正常系: 保存された暗号化キーが正しく復号されてロードされるか検証。"""
    plain_key = "saved-key-456"
    encrypted_key = SecurityManager.encrypt(plain_key)
    
    file_content = json.dumps({
        "encrypted_api_key": encrypted_key,
        "model": "gpt-5.2"
    })
    
    mock_config_file.exists.return_value = True
    
    # read_data を指定した mock_open を作成し、CONFIG_FILE.open に紐づける
    m_open = mock_open(read_data=file_content)
    mock_config_file.open.side_effect = m_open
    
    with patch.dict(os.environ, {}, clear=True):
        config = ConfigManager.load()
        assert config.api_key == plain_key

def test_load_resets_safety_defaults(mock_config_file):
    """[Config] Safety: ロード時に高コストな設定（Model, Reasoning）がデフォルトにリセットされるか検証。"""
    # ユーザーが以前高い設定を使用していた状態をシミュレート
    file_content = json.dumps({
        "model": "gpt-5.2-pro", 
        "reasoning_effort": "high",
        "last_response_id": "old_id"
    })
    
    mock_config_file.exists.return_value = True
    
    m_open = mock_open(read_data=file_content)
    mock_config_file.open.side_effect = m_open

    # SecurityManagerのモックは不要（ここではモデル設定に集中）
    with patch("src.config.app_config.SecurityManager.decrypt", return_value=None):
        config = ConfigManager.load()
        
        # 検証: 強制的にデフォルトに戻っているべき
        assert config.model == AppConfig.DEFAULT_MODEL
        assert config.reasoning_effort == AppConfig.DEFAULT_REASONING
        # コンテキストもリセット
        assert config.last_response_id is None

def test_load_malformed_json(mock_config_file):
    """[Config] 異常系: 設定ファイルが破損している(JSONエラー)場合のハンドリング。"""
    mock_config_file.exists.return_value = True
    
    m_open = mock_open(read_data="{ invalid json")
    mock_config_file.open.side_effect = m_open

    config = ConfigManager.load()
    # デフォルト設定が返されるはず
    assert config.model == AppConfig.DEFAULT_MODEL