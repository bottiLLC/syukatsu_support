"""バックアップマネージャー (backup_manager.py) のユニットテスト。"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from backup_manager import get_backup_dir, run_backup, set_backup_dir


def test_get_backup_dir_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """設定ファイルが存在しない場合、デフォルトのバックアップパスが返されることを検証します。"""
    monkeypatch.setattr("backup_manager._CONFIG_FILE", tmp_path / "nonexistent.json")
    monkeypatch.delenv("BACKUP_DIR", raising=False)
    backup_dir = get_backup_dir()
    assert backup_dir.name == "backups"


def test_set_and_get_backup_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """バックアップ保存先の更新と永続化された設定の取得を検証します。"""
    config_file = tmp_path / "data" / "backup_config.json"
    custom_target = tmp_path / "my_backups"
    monkeypatch.setattr("backup_manager._CONFIG_FILE", config_file)

    res = set_backup_dir(str(custom_target))
    assert res["success"] is True
    assert "バックアップ先を設定しました" in str(res["message"])

    resolved = get_backup_dir()
    assert resolved == custom_target.resolve()


def test_run_backup_empty_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """バックアップ元が空または未存在の場合、インターロックが働き処理が中断することを検証します。"""
    empty_dir = tmp_path / "empty_data"
    empty_dir.mkdir()
    res = run_backup(app_name="test_app", source_dir=str(empty_dir))

    assert res["success"] is False
    assert "バックアップ対象が存在しないか空欄です" in str(res["message"])


def test_run_backup_success_and_integrity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """正常系: アトミックZIP生成および testzip() による破損検知を通過することを検証します。"""
    source_dir = tmp_path / "data"
    source_dir.mkdir()
    test_file = source_dir / "sample.txt"
    test_file.write_text("TestDataContent", encoding="utf-8")

    backup_target = tmp_path / "dest_backups"
    monkeypatch.setattr("backup_manager._DEFAULT_BACKUP_DIR", backup_target)
    monkeypatch.setattr("backup_manager._CONFIG_FILE", tmp_path / "nonexistent.json")
    monkeypatch.delenv("BACKUP_DIR", raising=False)

    res = run_backup(app_name="test_app", source_dir=str(source_dir))
    assert res["success"] is True
    assert "バックアップ完了" in str(res["message"])

    dest_zip = Path(str(res["destination"]))
    assert dest_zip.exists()
    assert dest_zip.stat().st_size > 0

    with zipfile.ZipFile(dest_zip, "r") as zf:
        assert zf.testzip() is None
        assert "sample.txt" in zf.namelist()
        assert zf.read("sample.txt").decode("utf-8") == "TestDataContent"
