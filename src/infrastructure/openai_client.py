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

"""OpenAI API インフラストラクチャクライアント。

AsyncOpenAI を用いた Responses API および RAG (File/VectorStore) 管理の
実際の通信ロジックをカプセル化します。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import structlog
from openai import AsyncOpenAI, NotFoundError, OpenAIError
from openai.types import FileObject, FilePurpose
from openai.types.vector_store import VectorStore
from pydantic import ValidationError

from src.core.errors import translate_api_error
from src.core.resilience import resilient_api_call
from src.models import (
    ResponseRequestPayload,
    StreamError,
    StreamResponseCreated,
    StreamResult,
    StreamTextDelta,
    StreamUsage,
)

log = structlog.get_logger()


class OpenAIClient:
    """OpenAI の非同期クライアントをラップし、Responses API と RAG の機能を提供します。"""

    def __init__(self, api_key: str) -> None:
        """OpenAIClient を初期化します。

        Args:
            api_key: OpenAI API キー文字列
        """
        self.api_key = api_key

    def _get_client(self) -> AsyncOpenAI:
        """非同期 OpenAI クライアントインスタンスを生成して返します。"""
        return AsyncOpenAI(api_key=self.api_key)

    # --- Responses API ---

    async def stream_analysis(self, payload: ResponseRequestPayload) -> AsyncGenerator[StreamResult]:
        """リクエストペイロードに基づいて非同期ストリーミング分析を実行します。

        Args:
            payload: Responses API に送信する検証済みリクエストペイロード

        Yields:
            StreamResult: テキスト差分、トークン使用量、またはエラーイベント
        """
        try:
            request_params = payload.model_dump(exclude_none=True)
            log.info("Starting async stream analysis", model=payload.model)

            async for result in self._execute_stream(request_params):
                yield result

        except Exception as e:
            log.exception("Unexpected error in stream_analysis", error=str(e))
            yield StreamError(message=f"\n[Unexpected Error] 予期せぬエラーが発生しました: {e}")

    @resilient_api_call()
    async def _create_stream(self, client: AsyncOpenAI, request_params: dict[str, Any]) -> Any:
        """OpenAI Responses API ストリームを作成します。"""
        return await client.responses.create(**request_params)

    async def _execute_stream(self, request_params: dict[str, Any]) -> AsyncGenerator[StreamResult]:
        """ストリームイベントを受信・処理してジェネレータとして出力します。"""
        try:
            async with self._get_client() as client:
                stream = await self._create_stream(client, request_params)
                async for event in stream:
                    result = self._process_event(event)
                    if result:
                        yield result

        except OpenAIError as e:
            msg = translate_api_error(e)
            yield StreamError(message=f"\n{msg}")
        except ValidationError as e:
            yield StreamError(message=f"\n【バリデーションエラー】 リクエスト形式が不正です: {e}")
        except Exception as e:
            msg = translate_api_error(e)
            yield StreamError(message=f"\n{msg}")

    def _process_event(self, event: Any) -> StreamResult | None:
        """ストリームイベントを適切なドメインモデルに変換します。"""
        event_type = getattr(event, "type", None)
        if not event_type:
            return None

        if event_type == "response.output_text.delta":
            delta_content = getattr(event, "delta", None)
            return StreamTextDelta(delta=delta_content) if delta_content else None

        if event_type == "response.reasoning_text.delta":
            delta_content = getattr(event, "delta", None)
            return StreamTextDelta(delta=delta_content) if delta_content else None

        if event_type == "response.created":
            response_obj = getattr(event, "response", None)
            if response_obj and hasattr(response_obj, "id"):
                return StreamResponseCreated(response_id=response_obj.id)

        elif event_type == "response.completed":
            response_obj = getattr(event, "response", None)
            if not response_obj:
                return None
            usage_obj = getattr(response_obj, "usage", None)
            if not usage_obj:
                return None

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
            translated = translate_api_error(Exception(msg))
            return StreamError(message=f"\n{translated}")

        return None

    # --- RAG: Vector Stores ---

    @resilient_api_call()
    async def list_vector_stores(self, limit: int = 20) -> list[VectorStore]:
        """Vector Store の一覧を取得します。"""
        try:
            async with self._get_client() as client:
                res = await client.vector_stores.list(limit=limit)
                return list(res.data)
        except Exception as e:
            log.error("Failed to list vector stores", error=str(e))
            return []

    @resilient_api_call()
    async def create_vector_store(self, name: str) -> VectorStore:
        """新規 Vector Store を作成します。"""
        async with self._get_client() as client:
            return await client.vector_stores.create(name=name)

    @resilient_api_call()
    async def update_vector_store(self, vector_store_id: str, name: str) -> Any:
        """Vector Store の名称を更新します。"""
        async with self._get_client() as client:
            return await client.vector_stores.update(vector_store_id=vector_store_id, name=name)

    @resilient_api_call()
    async def delete_vector_store(self, vector_store_id: str) -> bool:
        """Vector Store を削除します。"""
        async with self._get_client() as client:
            res = await client.vector_stores.delete(vector_store_id=vector_store_id)
            return bool(res.deleted)

    @resilient_api_call()
    async def list_files_in_store(self, vector_store_id: str) -> list[Any]:
        """指定した Vector Store 内のファイル一覧を取得します。"""
        try:
            async with self._get_client() as client:
                res = await client.vector_stores.files.list(vector_store_id=vector_store_id)
                return list(res.data)
        except NotFoundError:
            return []

    @resilient_api_call()
    async def delete_file_from_store(self, vector_store_id: str, file_id: str) -> bool:
        """Vector Store からファイルを登録解除します。"""
        async with self._get_client() as client:
            res = await client.vector_stores.files.delete(vector_store_id=vector_store_id, file_id=file_id)
            return bool(res.deleted)

    # --- RAG: Files ---

    @resilient_api_call()
    async def upload_file(self, file_path: str, purpose: FilePurpose = "assistants") -> FileObject:
        """ローカルファイルを OpenAI Storage にアップロードします。"""
        path_obj = Path(file_path)
        if not path_obj.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        async with self._get_client() as client:
            with path_obj.open("rb") as f:
                res = await client.files.create(file=f, purpose=purpose)
            return res

    @resilient_api_call()
    async def delete_file(self, file_id: str) -> bool:
        """OpenAI Storage 上の物理ファイルを削除します。"""
        async with self._get_client() as client:
            res = await client.files.delete(file_id=file_id)
            return bool(res.deleted)

    @resilient_api_call()
    async def create_file_batch(self, vector_store_id: str, file_ids: list[str]) -> Any:
        """Vector Store に複数ファイルを一括登録（バッチインデックス）します。"""
        async with self._get_client() as client:
            return await client.vector_stores.file_batches.create(vector_store_id=vector_store_id, file_ids=file_ids)

    async def poll_batch_status(
        self, vector_store_id: str, batch_id: str, interval: float = 2.0, max_retries: int = 60
    ) -> str:
        """ファイルバッチのインデックス完了状態をポーリングします。"""
        for _ in range(max_retries):
            try:
                async with self._get_client() as client:
                    batch = await client.vector_stores.file_batches.retrieve(
                        vector_store_id=vector_store_id, batch_id=batch_id
                    )
                    if batch.status in ["completed", "failed", "cancelled"]:
                        return str(batch.status)
                await asyncio.sleep(interval)
            except Exception:
                await asyncio.sleep(interval)
        return "timed_out"
