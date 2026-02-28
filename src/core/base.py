"""
OpenAI APIとの通信を管理する基底サービスモジュール。

このモジュールは、OpenAI APIへのアクセスを必要とするすべてのサービスに対する抽象基底クラスを提供し、一貫した設定管理を保証します。
"""

import structlog

from openai import AsyncOpenAI
from typing import AsyncGenerator
from contextlib import asynccontextmanager

from src.config.app_config import AppConfig

# ロガーのセットアップ
log = structlog.get_logger()


class BaseOpenAIService:
    """
    OpenAI APIとやり取りするサービスの基底クラス。

    アプリケーションの全体規則に従い、リソースリークを防ぐために非同期コンテキストマネージャー内でAsyncOpenAIを使用することを強制します。

    Attributes:
        _api_key (str): 復号化されたOpenAI APIキー。
    """

    def __init__(self, api_key: str) -> None:
        """
        指定されたAPIキーでOpenAIサービスを初期化します。

        Args:
            api_key (str): 復号化されたOpenAI APIキー。

        Raises:
            ValueError: 提供されたAPIキーが空またはNoneの場合。
        """
        if not api_key:
            log.error("APIキーなしでBaseOpenAIServiceを初期化しようとしました。")
            raise ValueError("OpenAIサービスを初期化するにはAPIキーが必要です。")

        self._api_key = api_key

    @asynccontextmanager
    async def get_async_client(self) -> AsyncGenerator[AsyncOpenAI, None]:
        """
        AsyncOpenAIクライアントを生成するコンテキストマネージャー。
        非同期HTTPセッションの適切な作成とクリーンアップを保証します。

        Yields:
            AsyncOpenAI: 設定済みの非同期OpenAIクライアント。
        """
        client = AsyncOpenAI(
            api_key=self._api_key,
            timeout=AppConfig.API_TIMEOUT,
            max_retries=AppConfig.API_MAX_RETRIES,
        )
        try:
            yield client
        finally:
            await client.close()
