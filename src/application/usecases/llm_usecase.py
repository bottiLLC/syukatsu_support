# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
LLM分析の実行とストリーミング管理を担当するUseCaseモジュール。
"""

import asyncio
import structlog
from typing import AsyncGenerator

from src.models import ResponseRequestPayload, StreamResult, StreamTextDelta, StreamError
from src.infrastructure.openai_client import OpenAIClient

log = structlog.get_logger()

class LLMUseCase:
    """
    LLMに関するビジネスロジックを実行するクラス。
    Fletのネイティブな非同期環境に対応し、結果を直接非同期ジェネレータで返します。
    """
    def __init__(self, client: OpenAIClient):
        self.client = client

    async def execute_analysis_stream(self, payload: ResponseRequestPayload, cancel_event: asyncio.Event = None) -> AsyncGenerator[StreamResult, None]:
        """
        ストリーミング分析を実行する非同期ジェネレータ。
        
        Args:
            payload (ResponseRequestPayload): リクエスト情報。
            cancel_event (asyncio.Event, optional): キャンセル検知用イベント。
            
        Yields:
            StreamResult: ストリーミングイベント。
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
