"""
OpenAI API インフラストラクチャクライアント。

AsyncOpenAI を用いた Responses API および RAG (File/VectorStore) 管理の
実際の通信ロジックをカプセル化します。
"""

import asyncio
import structlog
from pathlib import Path
from typing import Any, AsyncGenerator, List, Optional
from openai import AsyncOpenAI, OpenAIError, NotFoundError
from openai.types import FileObject
from pydantic import ValidationError

from src.models import (
    ResponseRequestPayload,
    StreamResult,
    StreamTextDelta,
    StreamResponseCreated,
    StreamUsage,
    StreamError,
)
from src.core.errors import translate_api_error
from src.core.resilience import resilient_api_call

log = structlog.get_logger()


class OpenAIClient:
    """
    OpenAI の非同期クライアントをラップし、Responses API と RAG の機能を提供します。
    """
    def __init__(self, api_key: str):
        self.api_key = api_key

    def _get_client(self) -> AsyncOpenAI:
        return AsyncOpenAI(api_key=self.api_key)

    # --- Responses API ---

    async def stream_analysis(
        self, payload: ResponseRequestPayload
    ) -> AsyncGenerator[StreamResult, None]:
        try:
            request_params = payload.model_dump(exclude_none=True)
            log.info("Starting async stream analysis", model=payload.model)

            async for result in self._execute_stream(request_params):
                yield result

        except Exception as e:
            log.exception("Unexpected error in stream_analysis", error=str(e))
            yield StreamError(message=f"\n[Unexpected Error] 予期せぬエラーが発生しました: {e}")

    @resilient_api_call()
    async def _create_stream(self, client: AsyncOpenAI, request_params: dict) -> Any:
        return await client.responses.create(**request_params)

    async def _execute_stream(self, request_params: dict) -> AsyncGenerator[StreamResult, None]:
        model_name = request_params.get("model", "unknown")
        try:
            async with self._get_client() as client:
                stream = await self._create_stream(client, request_params)
                async for event in stream:
                    result = self._process_event(event)
                    if result:
                        yield result

        except OpenAIError as e:
            msg = translate_api_error(e)
            yield StreamError(message=f"\n[API Error] {msg}")
        except ValidationError as e:
            yield StreamError(message=f"\n[Validation Error] リクエスト形式が不正です: {e}")
        except Exception as e:
            yield StreamError(message=f"\n[Stream Error] ストリーム処理エラー: {e}")

    def _process_event(self, event: Any) -> Optional[StreamResult]:
        event_type = getattr(event, "type", None)
        if not event_type:
            return None

        if event_type == "response.output_text.delta":
            delta_content = getattr(event, "delta", None)
            return StreamTextDelta(delta=delta_content) if delta_content else None
            
        elif event_type == "response.created":
            response_obj = getattr(event, "response", None)
            if response_obj and hasattr(response_obj, "id"):
                return StreamResponseCreated(response_id=response_obj.id)
            
        elif event_type == "response.completed":
            response_obj = getattr(event, "response", None)
            if not response_obj: return None
            usage_obj = getattr(response_obj, "usage", None)
            if not usage_obj: return None
            
            input_tokens = getattr(usage_obj, "input_tokens", 0)
            output_tokens = getattr(usage_obj, "output_tokens", 0)
            total_tokens = getattr(usage_obj, "total_tokens", 0)
            
            cached_tokens = 0
            input_details = getattr(usage_obj, "input_tokens_details", None)
            if input_details:
                cached_tokens = getattr(input_details, "cached_tokens", 0)
                
            return StreamUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cached_tokens=cached_tokens,
            )
            
        elif event_type == "error":
            error_obj = getattr(event, "error", None)
            msg = "Unknown stream error"
            if error_obj:
                msg = getattr(error_obj, "message", str(error_obj))
            return StreamError(message=f"\n[Stream Error] {msg}")

        return None

    # --- RAG: Vector Stores ---

    @resilient_api_call()
    async def list_vector_stores(self, limit: int = 20) -> List[Any]:
        try:
            async with self._get_client() as client:
                res = await client.vector_stores.list(limit=limit)
                return list(res.data)
        except Exception as e:
            log.error("Failed to list vector stores", error=str(e))
            return []

    @resilient_api_call()
    async def create_vector_store(self, name: str) -> Any:
        async with self._get_client() as client:
            return await client.vector_stores.create(name=name)

    @resilient_api_call()
    async def delete_vector_store(self, vector_store_id: str) -> bool:
        async with self._get_client() as client:
            res = await client.vector_stores.delete(vector_store_id=vector_store_id)
            return res.deleted

    @resilient_api_call()
    async def list_files_in_store(self, vector_store_id: str) -> List[Any]:
        try:
            async with self._get_client() as client:
                res = await client.vector_stores.files.list(vector_store_id=vector_store_id)
                return list(res.data)
        except NotFoundError:
            return []

    @resilient_api_call()
    async def delete_file_from_store(self, vector_store_id: str, file_id: str) -> bool:
        async with self._get_client() as client:
            res = await client.vector_stores.files.delete(
                vector_store_id=vector_store_id, file_id=file_id
            )
            return res.deleted

    # --- RAG: Files ---

    @resilient_api_call()
    async def upload_file(self, file_path: str, purpose: str = "assistants") -> FileObject:
        path_obj = Path(file_path)
        if not path_obj.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        async with self._get_client() as client:
            with path_obj.open("rb") as f:
                res = await client.files.create(file=f, purpose=purpose)
            return res

    @resilient_api_call()
    async def delete_file(self, file_id: str) -> bool:
        async with self._get_client() as client:
            res = await client.files.delete(file_id=file_id)
            return res.deleted

    @resilient_api_call()
    async def create_file_batch(self, vector_store_id: str, file_ids: List[str]) -> Any:
        async with self._get_client() as client:
            return await client.vector_stores.file_batches.create(
                vector_store_id=vector_store_id, file_ids=file_ids
            )

    async def poll_batch_status(
        self, vector_store_id: str, batch_id: str, interval: float = 2.0, max_retries: int = 60
    ) -> str:
        for _ in range(max_retries):
            try:
                async with self._get_client() as client:
                    batch = await client.vector_stores.file_batches.retrieve(
                        vector_store_id=vector_store_id, batch_id=batch_id
                    )
                    if batch.status in ["completed", "failed", "cancelled"]:
                        return batch.status
                await asyncio.sleep(interval)
            except Exception:
                await asyncio.sleep(interval)
        return "timed_out"

