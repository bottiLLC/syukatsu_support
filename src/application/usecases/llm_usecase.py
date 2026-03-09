"""
LLM分析の実行とストリーミング管理を担当するUseCaseモジュール。
"""

import asyncio
import queue
import threading
import structlog

from src.models import ResponseRequestPayload, StreamTextDelta, StreamError
from src.infrastructure.openai_client import OpenAIClient

log = structlog.get_logger()

class LLMUseCase:
    """
    LLMに関するビジネスロジックを実行するクラス。
    UIスレッドをブロックしないよう別スレッドでの非同期実行をカプセル化し、
    結果をキューを介して呼び出し元（UI/State層）へ中継します。
    """
    def __init__(self, client: OpenAIClient, message_queue: queue.Queue, cancel_event: threading.Event):
        self.client = client
        self.message_queue = message_queue
        self.cancel_event = cancel_event

    def execute_analysis_thread(self, payload: ResponseRequestPayload) -> threading.Thread:
        """
        別スレッドでストリーミング分析を開始し、Threadオブジェクトを返します。
        
        Args:
            payload (ResponseRequestPayload): リクエスト情報。
            
        Returns:
            threading.Thread: 開始されたスレッドオブジェクト。
        """
        thread = threading.Thread(
            target=self._run_llm_thread,
            args=(payload,),
            daemon=True,
        )
        thread.start()
        return thread

    def _run_llm_thread(self, payload: ResponseRequestPayload) -> None:
        """
        内部的に非同期イベントループを立ち上げてストリーミングを処理するメソッド。
        """
        async def _async_run():
            try:
                start_msg = f"\n[AI ({payload.model})] analyzing...\n（数分から10分程度の時間を要する場合があります。）\n\n"
                self.message_queue.put(StreamTextDelta(delta=start_msg))

                stream = self.client.stream_analysis(payload)
                async for event in stream:
                    # キャンセルイベントがセットされたら直ちに中断する
                    if self.cancel_event.is_set():
                        break
                    self.message_queue.put(event)

            except Exception as e:
                log.exception("LLM thread failed", error=str(e))
                self.message_queue.put(StreamError(message=str(e)))
            finally:
                self.message_queue.put(None)

        asyncio.run(_async_run())
