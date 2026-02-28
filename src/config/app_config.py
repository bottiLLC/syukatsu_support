"""
就活サポートアプリの設定（Configuration）モジュール。

このモジュールは以下を処理します：
1. ローカル暗号化（Fernet）を使用したAPIキーの安全な管理。
2. JSONおよび環境変数を経由したユーザー設定の読み込みと保存。
3. アプリケーションの定数およびデフォルト設定の定義。
"""

import json
import os
import structlog
from pathlib import Path
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

from src.types import ReasoningEffort

# .envファイルから環境変数を読み込む（存在する場合）
load_dotenv()

# ロガーのセットアップ
log = structlog.get_logger()

# 定数
# パスは現在の作業ディレクトリ（CWD）からの相対パス
CONFIG_FILE = Path("config.json")
KEY_FILE = Path(".secret.key")


class AppConfig:
    """
    グローバルなアプリケーション設定の定数を定義します。

    Attributes:
        APP_VERSION (str): アプリケーションの現在のバージョン。
        DEFAULT_MODEL (str): デフォルトのOpenAIモデル（gpt-5.2をターゲット）。
        DEFAULT_REASONING (ReasoningEffort): デフォルトの推論エフォートレベル（reasoning effort）。
        API_TIMEOUT (float): API呼び出しのグローバルタイムアウト（秒）。
        API_MAX_RETRIES (int): 失敗したAPI呼び出しのリトライ回数。
    """

    APP_VERSION: str = "v1.0.0"

    # 起動時に強制するデフォルト設定（安全性とコスト管理のため）
    DEFAULT_MODEL: str = "gpt-5.2"
    DEFAULT_REASONING: ReasoningEffort = "high"

    API_TIMEOUT: float = 1200.0
    API_MAX_RETRIES: int = 2


class UserConfig(BaseModel):
    """
    実行時のユーザー設定を表すPydanticモデル。

    このモデルはメモリ内に*復号化された*APIキーを保持します。
    プレーンテキストの漏洩を防ぐため、直接ディスクにはダンプ（保存）されません。
    """

    model_config = {"populate_by_name": True}

    api_key: Optional[str] = Field(
        default=None, description="復号化されたOpenAI APIキー。"
    )
    model: str = Field(
        default=AppConfig.DEFAULT_MODEL, description="選択されたOpenAIモデルのID。"
    )
    reasoning_effort: ReasoningEffort = Field(
        default=AppConfig.DEFAULT_REASONING,
        description="モデルの推論エフォート（reasoning effort）レベル。",
    )
    # FIX: Corrected string to match src/core/prompts.py (Added space)
    system_prompt_mode: str = Field(
        default="有価証券報告書 -財務分析-",
        description="現在選択されている分析戦略モード。",
    )
    last_response_id: Optional[str] = Field(
        default=None,
        description="コンテキストの継続性を保つための最後のレスポンスID。",
    )

    # --- RAG設定 ---
    current_vector_store_id: Optional[str] = Field(
        default=None, description="現在選択されているVector StoreのID。"
    )
    use_file_search: bool = Field(
        default=False, description="File Search (RAG) ツールを有効にするかどうか。"
    )


class SecurityManager:
    """
    Fernetを使用して、機密データのローカル暗号化および復号化を処理します。
    """

    @staticmethod
    def _get_or_create_key() -> bytes:
        """
        ディスクから暗号化キーを取得するか、新しいキーを生成します。

        Returns:
            bytes: Fernetの暗号化キー。

        Raises:
            IOError: キーファイルの読み書きに失敗した場合。
        """
        if KEY_FILE.exists():
            try:
                return KEY_FILE.read_bytes()
            except IOError as e:
                log.error("キーファイルの読み込みに失敗しました", error=str(e), path=str(KEY_FILE))
                raise

        # 存在しない場合は新しいキーを生成
        log.info("新しい暗号化キーを生成しています。")
        key = Fernet.generate_key()
        try:
            KEY_FILE.write_bytes(key)
            # POSIXシステムでは制限の厳しい権限（オーナーのみ読み書き可能）を設定
            if os.name == "posix":
                KEY_FILE.chmod(0o600)
        except IOError as e:
            log.critical("暗号化キーの保存に失敗しました", error=str(e), path=str(KEY_FILE))
            raise
        return key

    @classmethod
    def encrypt(cls, plain_text: str) -> str:
        """
        文字列を暗号化します。

        Args:
            plain_text: 暗号化するテキスト。

        Returns:
            暗号化されたテキスト文字列。入力が空またはエラーの場合は空文字列。
        """
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
        """
        文字列を復号化します。

        Args:
            cipher_text: 暗号化されたテキスト文字列。

        Returns:
            復号化されたテキスト。復号化に失敗した場合は None。
        """
        if not cipher_text:
            return None
        try:
            fernet = Fernet(cls._get_or_create_key())
            return fernet.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
        except (InvalidToken, Exception) as e:
            log.warning(
                "復号化に失敗しました。シークレットキーが再生成されたか、データが破損している可能性があります。",
                error=str(e)
            )
            return None


class ConfigManager:
    """
    アプリケーション設定の読み込みおよび保存のためのサービス。

    APIキーがディスク上では暗号化され、メモリ内では復号化されていることを保証します。
    複数セッションにわたる高価なモデルの使用を防ぐため、ロード時にデフォルト設定を強制します。
    """

    @staticmethod
    def load() -> UserConfig:
        """
        ディスクおよび環境変数から設定を読み込みます。

        優先順位:
        1. 環境変数 (OPENAI_API_KEY) - 最も高いセキュリティ優先度。
        2. 設定ファイル (暗号化されたAPIキー) - GUIユーザーのための永続化。

        安全性:
            複数セッションにわたる高価なモデルの使用を防ぐため、
            モデルと推論エフォート（Reasoning Effort）はロード時に常にデフォルトにリセットされます。

        Returns:
            UserConfig: 読み込まれた設定オブジェクト。
        """
        config_data: Dict[str, Any] = {}

        # 1. JSONファイルからの読み込み（主にAPIキーの永続化のため）
        if CONFIG_FILE.exists():
            try:
                with CONFIG_FILE.open("r", encoding="utf-8") as f:
                    file_data = json.load(f)

                # 'encrypted_api_key' が存在する場合はAPIキーを復号化
                encrypted_key = file_data.get("encrypted_api_key")
                if encrypted_key:
                    decrypted_key = SecurityManager.decrypt(encrypted_key)
                    if decrypted_key:
                        file_data["api_key"] = decrypted_key
                    else:
                        # 復号化に失敗した場合、不正なデータを渡さないようにする
                        log.warning("復号化に失敗したため、APIキーをリセットしています。")
                        file_data["api_key"] = None

                # Pydanticの初期化に使用される辞書から暗号化されたフィールドを削除
                file_data.pop("encrypted_api_key", None)
                config_data = file_data

            except (json.JSONDecodeError, IOError, Exception) as e:
                log.error("設定ファイルの読み込みに失敗しました", error=str(e), path=str(CONFIG_FILE))

        # 2. 環境変数による上書き（ファイルベースのキーが存在する場合は上書き）
        env_key = os.getenv("OPENAI_API_KEY")
        if env_key:
            config_data["api_key"] = env_key

        # 3. 安全性に基づくデフォルト値の強制（保存されているモデル/推論設定を無視）
        config_data["model"] = AppConfig.DEFAULT_MODEL
        config_data["reasoning_effort"] = AppConfig.DEFAULT_REASONING

        # 新規スタートのためにプロンプトモードとコンテキストをリセット
        # FIX: Ensure consistency with prompts.py
        config_data["system_prompt_mode"] = "有価証券報告書 -財務分析-"
        config_data["last_response_id"] = None

        # RAG設定（use_file_search、current_vector_store_id）は読み込まれた場合保持される

        # バリデーションと返却
        try:
            return UserConfig(**config_data)
        except ValidationError as e:
            log.error("設定のバリデーションに失敗しました", error=str(e))
            # デフォルト設定にフォールバック
            return UserConfig()

    @staticmethod
    def save(config: UserConfig) -> None:
        """
        設定をディスクに保存します。

        'api_key' フィールドはプレーンテキストのダンプから明示的に除外され、
        'encrypted_api_key' 内に安全に保存されます。

        Args:
            config: 保存する現在の設定状態。
        """
        try:
            # 1. 辞書に変換し、機密フィールドを明示的に除外
            data = config.model_dump(exclude={"api_key"})

            # 2. APIキーを暗号化して手動で追加
            if config.api_key:
                encrypted = SecurityManager.encrypt(config.api_key)
                if encrypted:
                    data["encrypted_api_key"] = encrypted

            # 3. ディスクへ書き出し
            with CONFIG_FILE.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)

            log.info("設定が正常に保存されました。", path=str(CONFIG_FILE))
        except IOError as e:
            log.error("設定の保存に失敗しました", error=str(e), path=str(CONFIG_FILE))