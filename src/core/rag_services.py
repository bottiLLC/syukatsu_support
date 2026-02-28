"""
RAG（検索拡張生成）サービスモジュール。

このモジュールは、就活サポートアプリのRAG機能におけるファイルアップロードと
Vector Storeの管理を処理します。AsyncOpenAIコンテキストマネージャーを使用し、
OpenAI API仕様に準拠しています。
"""

import asyncio
import structlog
from pathlib import Path
from typing import Any, List, Optional

from openai import NotFoundError
from openai.types import FileObject

from src.core.base import BaseOpenAIService
from src.core.resilience import resilient_api_call

log = structlog.get_logger()


class FileService(BaseOpenAIService):
    """
    OpenAI APIを介してファイルを管理するサービス。

    ファイルのアップロード、詳細情報の取得、削除を非同期で処理します。
    """

    @resilient_api_call()
    async def upload_file(self, file_path: str, purpose: str = "assistants") -> FileObject:
        """
        ファイルを非同期でOpenAIにアップロードします。

        Args:
            file_path (str): ファイルへのローカルパス。
            purpose (str): ファイルの目的。デフォルトは "assistants"。

        Returns:
            FileObject: APIからアップロードされたファイルオブジェクト。

        Raises:
            FileNotFoundError: ローカルファイルが存在しない場合。
            Exception: API呼び出しが失敗した場合。
        """
        path_obj = Path(file_path)
        if not path_obj.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        log.info("Uploading file async", file_path=file_path, purpose=purpose)
        try:
            async with self.get_async_client() as client:
                with path_obj.open("rb") as f:
                    response = await client.files.create(file=f, purpose=purpose)
                log.info("File uploaded successfully", file_id=response.id)
                return response
        except Exception as e:
            log.error("Failed to upload file", error=str(e), file_path=file_path)
            raise

    @resilient_api_call()
    async def get_file_details(self, file_id: str) -> Optional[FileObject]:
        """
        特定のファイルのメタデータを非同期で取得します。
        """
        try:
            async with self.get_async_client() as client:
                return await client.files.retrieve(file_id=file_id)
        except Exception as e:
            log.error("Failed to retrieve file details", error=str(e), file_id=file_id)
            return None

    @resilient_api_call()
    async def delete_file(self, file_id: str) -> bool:
        """
        OpenAIからファイルを非同期で削除します（完全削除）。
        """
        log.info("Deleting file async", file_id=file_id)
        try:
            async with self.get_async_client() as client:
                response = await client.files.delete(file_id=file_id)
                return response.deleted
        except Exception as e:
            log.error("Failed to delete file", error=str(e), file_id=file_id)
            raise


class VectorStoreService(BaseOpenAIService):
    """
    非同期OpenAI APIを使用して、Vector Storeとファイルバッチを管理するサービス。
    """

    @resilient_api_call()
    async def list_vector_stores(self, limit: int = 20) -> List[Any]:
        """
        利用可能なVector Storeを非同期でリスト化します。
        """
        try:
            async with self.get_async_client() as client:
                response = await client.vector_stores.list(limit=limit)
                return list(response.data)
        except Exception as e:
            log.error("Failed to list vector stores", error=str(e))
            return []

    @resilient_api_call()
    async def create_vector_store(self, name: str) -> Any:
        """
        新しいVector Storeを非同期で作成します。
        """
        log.info("Creating vector store async", name=name)
        try:
            async with self.get_async_client() as client:
                return await client.vector_stores.create(name=name)
        except Exception as e:
            log.error("Failed to create vector store", error=str(e), name=name)
            raise

    @resilient_api_call()
    async def update_vector_store(self, vector_store_id: str, name: str) -> Any:
        """
        Vector Storeの名前を非同期で更新します。
        """
        log.info("Updating vector store", vector_store_id=vector_store_id, name=name)
        try:
            async with self.get_async_client() as client:
                return await client.vector_stores.update(
                    vector_store_id=vector_store_id, name=name
                )
        except Exception as e:
            log.error("Failed to update vector store", error=str(e), vector_store_id=vector_store_id)
            raise

    @resilient_api_call()
    async def delete_vector_store(self, vector_store_id: str) -> bool:
        """
        Vector Storeを非同期で削除します。
        """
        log.info("Deleting vector store async", vector_store_id=vector_store_id)
        try:
            async with self.get_async_client() as client:
                response = await client.vector_stores.delete(
                    vector_store_id=vector_store_id
                )
                return response.deleted
        except Exception as e:
            log.error("Failed to delete vector store", error=str(e), vector_store_id=vector_store_id)
            raise

    @resilient_api_call()
    async def create_file_batch(self, vector_store_id: str, file_ids: List[str]) -> Any:
        """
        Vector Storeにファイルを追加するための非同期ファイルバッチを作成します。
        """
        log.info("Creating async file batch", vector_store_id=vector_store_id, file_count=len(file_ids))
        try:
            async with self.get_async_client() as client:
                return await client.vector_stores.file_batches.create(
                    vector_store_id=vector_store_id, file_ids=file_ids
                )
        except Exception as e:
            log.error("Failed to create file batch", error=str(e), vector_store_id=vector_store_id)
            raise

    # poll_batch_status handles retries internally through the while loop,
    # so resilient_api_call might interfere during the polling process.
    async def poll_batch_status(
        self,
        vector_store_id: str,
        batch_id: str,
        interval: float = 2.0,
        max_retries: int = 60,
    ) -> str:
        """
        バッチのステータスが完了、失敗、またはタイムアウトになるまで、非同期でポーリングします。
        """
        log.info("Polling async batch status...", batch_id=batch_id)
        for _ in range(max_retries):
            try:
                async with self.get_async_client() as client:
                    batch = await client.vector_stores.file_batches.retrieve(
                        vector_store_id=vector_store_id, batch_id=batch_id
                    )
                    status = batch.status

                    if status in ["completed", "failed", "cancelled"]:
                        log.info("Batch finished", batch_id=batch_id, status=status)
                        if status == "completed":
                            counts = getattr(batch, "file_counts", None)
                            log.info("Batch file counts", batch_id=batch_id, counts=counts)
                        return status

                await asyncio.sleep(interval)
            except Exception as e:
                log.error("Error polling batch status", error=str(e), batch_id=batch_id)
                await asyncio.sleep(interval)

        log.error("Polling timed out for batch", batch_id=batch_id)
        return "timed_out"

    @resilient_api_call()
    async def list_files_in_store(self, vector_store_id: str) -> List[Any]:
        """
        Vector Store内の現在のファイルを非同期でリスト化します。
        """
        try:
            async with self.get_async_client() as client:
                response = await client.vector_stores.files.list(
                    vector_store_id=vector_store_id
                )
                return list(response.data)
        except NotFoundError:
            return []
        except Exception as e:
            log.error("Failed to list files in store", error=str(e), vector_store_id=vector_store_id)
            return []

    @resilient_api_call()
    async def delete_file_from_store(self, vector_store_id: str, file_id: str) -> bool:
        """
        Vector Storeからファイルを非同期で削除します。
        """
        log.info("Removing file from store", file_id=file_id, vector_store_id=vector_store_id)
        try:
            async with self.get_async_client() as client:
                response = await client.vector_stores.files.delete(
                    vector_store_id=vector_store_id, file_id=file_id
                )
                return response.deleted
        except Exception as e:
            log.error("Failed to remove file from store", error=str(e), file_id=file_id, vector_store_id=vector_store_id)
            raise
