"""
セキュリティおよびデータ永続化モジュール。

APIキーの安全な暗号化/復号化（Fernet）および
設定ファイル（config.json）の読み書きを処理します。
"""

import json
import os
import structlog
from pathlib import Path
from typing import Dict, Any, Optional
from cryptography.fernet import Fernet, InvalidToken
from pydantic import ValidationError

from src.models import UserConfig, AppConfigDefaults

log = structlog.get_logger()

# パス設定（CWDからの相対パス）
CONFIG_FILE = Path("config.json")
KEY_FILE = Path(".secret.key")


class SecurityManager:
    @staticmethod
    def _get_or_create_key() -> bytes:
        if KEY_FILE.exists():
            try:
                return KEY_FILE.read_bytes()
            except IOError as e:
                log.error("キーファイルの読み込みに失敗しました", error=str(e), path=str(KEY_FILE))
                raise

        log.info("新しい暗号化キーを生成しています。")
        key = Fernet.generate_key()
        try:
            KEY_FILE.write_bytes(key)
            if os.name == "posix":
                KEY_FILE.chmod(0o600)
        except IOError as e:
            log.critical("暗号化キーの保存に失敗しました", error=str(e), path=str(KEY_FILE))
            raise
        return key

    @classmethod
    def encrypt(cls, plain_text: str) -> str:
        if not plain_text:
            return ""
        try:
            fernet = Fernet(cls._get_or_create_key())
            return fernet.encrypt(plain_text.encode("utf-8")).decode("utf-8")
        except Exception as e:
            log.error("暗号化に失敗しました", error=str(e))
            return ""

    @classmethod
    def decrypt(cls, cipher_text: str) -> Optional[str]:
        if not cipher_text:
            return None
        try:
            fernet = Fernet(cls._get_or_create_key())
            return fernet.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
        except (InvalidToken, Exception) as e:
            log.warning("復号化に失敗しました", error=str(e))
            return None


class ConfigManager:
    @staticmethod
    def load() -> UserConfig:
        config_data: Dict[str, Any] = {}

        if CONFIG_FILE.exists():
            try:
                with CONFIG_FILE.open("r", encoding="utf-8") as f:
                    file_data = json.load(f)

                encrypted_key = file_data.get("encrypted_api_key")
                if encrypted_key:
                    decrypted_key = SecurityManager.decrypt(encrypted_key)
                    if decrypted_key:
                        file_data["api_key"] = decrypted_key
                    else:
                        file_data["api_key"] = None

                file_data.pop("encrypted_api_key", None)
                config_data = file_data

            except Exception as e:
                log.error("設定ファイルの読み込みに失敗しました", error=str(e), path=str(CONFIG_FILE))

        env_key = os.getenv("OPENAI_API_KEY")
        if env_key:
            config_data["api_key"] = env_key

        # 環境のリセット（高コストモデル防止）
        config_data["model"] = AppConfigDefaults.DEFAULT_MODEL
        config_data["reasoning_effort"] = AppConfigDefaults.DEFAULT_REASONING
        config_data["system_prompt_mode"] = "有価証券報告書 -財務分析-"
        config_data["last_response_id"] = None

        try:
            return UserConfig(**config_data)
        except ValidationError as e:
            log.error("設定のバリデーションに失敗しました", error=str(e))
            return UserConfig()

    @staticmethod
    def save(config: UserConfig) -> None:
        try:
            data = config.model_dump(exclude={"api_key"})
            if config.api_key:
                encrypted = SecurityManager.encrypt(config.api_key)
                if encrypted:
                    data["encrypted_api_key"] = encrypted

            with CONFIG_FILE.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)

            log.info("設定が正常に保存されました。", path=str(CONFIG_FILE))
        except IOError as e:
            log.error("設定の保存に失敗しました", error=str(e), path=str(CONFIG_FILE))
