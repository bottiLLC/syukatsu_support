# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""セキュリティおよび設定管理モジュール (src/infrastructure/security.py) のユニットテスト。"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.infrastructure.security import (
    ConfigManager,
    SecurityManager,
    ensure_storage_initialized,
)
from src.models import AppConfigDefaults, UserConfig


def test_ensure_storage_initialized_creates_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ストレージディレクトリが存在しない場合に正しく生成されることを検証します。"""
    # Arrange
    target_data = tmp_path / "data"
    monkeypatch.setattr("src.infrastructure.security.DATA_DIR", target_data)
    monkeypatch.setattr("src.infrastructure.security.CONFIG_FILE", target_data / "config.json")
    monkeypatch.setattr("src.infrastructure.security.KEY_FILE", target_data / ".secret.key")

    # Act
    ensure_storage_initialized()

    # Assert
    assert target_data.exists()
    assert target_data.is_dir()


def test_security_manager_encrypt_and_decrypt_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """平文の暗号化と復号化が正しく往復変換できることを検証します。"""
    # Arrange
    target_data = tmp_path / "data"
    monkeypatch.setattr("src.infrastructure.security.DATA_DIR", target_data)
    monkeypatch.setattr("src.infrastructure.security.CONFIG_FILE", target_data / "config.json")
    monkeypatch.setattr("src.infrastructure.security.KEY_FILE", target_data / ".secret.key")
    raw_secret = "sk-proj-test-secret-key-12345"

    # Act
    cipher = SecurityManager.encrypt(raw_secret)
    decrypted = SecurityManager.decrypt(cipher)

    # Assert
    assert cipher != raw_secret
    assert len(cipher) > 0
    assert decrypted == raw_secret


def test_security_manager_empty_and_invalid_inputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """空文字列および不正な暗号文に対して安全にデフォルト値を返すことを検証します。"""
    # Arrange
    target_data = tmp_path / "data"
    monkeypatch.setattr("src.infrastructure.security.DATA_DIR", target_data)
    monkeypatch.setattr("src.infrastructure.security.CONFIG_FILE", target_data / "config.json")
    monkeypatch.setattr("src.infrastructure.security.KEY_FILE", target_data / ".secret.key")

    # Act & Assert
    assert SecurityManager.encrypt("") == ""
    assert SecurityManager.decrypt("") is None
    assert SecurityManager.decrypt("invalid-base64-not-a-token") is None


def test_config_manager_save_and_load(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """UserConfig の永続化とロードが暗号化キーを保持して正しく動作することを検証します。"""
    # Arrange
    target_data = tmp_path / "data"
    monkeypatch.setattr("src.infrastructure.security.DATA_DIR", target_data)
    monkeypatch.setattr("src.infrastructure.security.CONFIG_FILE", target_data / "config.json")
    monkeypatch.setattr("src.infrastructure.security.KEY_FILE", target_data / ".secret.key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    test_config = UserConfig(
        api_key="sk-proj-saved-key-abc",
        current_vector_store_id="vs_123456",
        use_file_search=True,
    )

    # Act
    ConfigManager.save(test_config)
    loaded = ConfigManager.load()

    # Assert
    assert loaded.api_key == "sk-proj-saved-key-abc"
    assert loaded.current_vector_store_id == "vs_123456"
    assert loaded.use_file_search is True
    # Invariant overrides
    assert loaded.model == AppConfigDefaults.DEFAULT_MODEL
    assert loaded.reasoning_effort == AppConfigDefaults.DEFAULT_REASONING
