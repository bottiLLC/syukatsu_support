"""LLM分析の実行とストリーミング管理を担当するユースケースモジュール。

OpenAI API client を利用してストリーミング分析の実行制御およびキャンセルイベント管理を行います。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

import structlog

from src.infrastructure.openai_client import OpenAIClient
from src.models import ResponseRequestPayload, StreamError, StreamResult, StreamTextDelta

log = structlog.get_logger()


class LLMUseCase:
    """LLMに関するビジネスロジックを実行するユースケースクラス。"""

    def __init__(self, client: OpenAIClient) -> None:
        """LLMUseCase を初期化します。

        Args:
            client: OpenAI インフラストラクチャクライアント
        """
        self.client = client

    async def execute_analysis_stream(
        self, payload: ResponseRequestPayload, cancel_event: asyncio.Event | None = None
    ) -> AsyncGenerator[StreamResult]:
        """ストリーミング分析を実行し、イベントを逐次 yield します。

        Args:
            payload: リクエスト情報
            cancel_event: ユーザーによる処理中断検知用イベント

        Yields:
            StreamResult: テキスト差分またはエラーイベント
        """
        try:
            start_msg = f"\n[AI ({payload.model})] analyzing...\n（数分から10分程度の時間を要する場合があります。）\n\n"
            yield StreamTextDelta(delta=start_msg)

            stream = self.client.stream_analysis(payload)
            async for event in stream:
                if cancel_event and cancel_event.is_set():
                    break
                yield event

        except Exception as e:
            log.exception("LLM stream failed", error=str(e))
            yield StreamError(message=str(e))
