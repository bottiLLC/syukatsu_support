"""
基底サービスモジュール (src/core/base.py) のユニットテスト。
"""

from unittest.mock import patch, AsyncMock

import pytest

from src.config.app_config import AppConfig
from src.core.base import BaseOpenAIService

pytestmark = pytest.mark.asyncio

class TestBaseOpenAIService:
    """抽象基底クラスの初期化に関するテスト。"""

    async def test_init_success(self):
        """正しい設定でクライアントが初期化されることを検証します。"""
        # 実際のネットワーク通信やキーの検証を避けるためにAsyncOpenAIをモック化
        with patch("src.core.base.AsyncOpenAI") as MockAsyncOpenAI:
            MockAsyncOpenAI.return_value.close = AsyncMock()
            service = BaseOpenAIService(api_key="test-key")

            # コンテキストマネージャー使用時にAsyncOpenAIが期待されるパラメータで呼び出されるか確認
            async with service.get_async_client() as client:
                assert client == MockAsyncOpenAI.return_value

            MockAsyncOpenAI.assert_called_once()
            _, kwargs = MockAsyncOpenAI.call_args

            assert kwargs["api_key"] == "test-key"
            assert kwargs["timeout"] == AppConfig.API_TIMEOUT
            assert kwargs["max_retries"] == AppConfig.API_MAX_RETRIES

            # クローズメソッドが呼ばれたか検証
            client.close.assert_awaited_once()

    async def test_init_missing_key(self):
        """APIキーが欠如している場合にValueErrorが発生することを検証します。"""
        # 空文字列のテスト
        with pytest.raises(ValueError):
            BaseOpenAIService(api_key="")

        # Noneのテスト
        with pytest.raises(ValueError):
            BaseOpenAIService(api_key=None)  # type: ignore
