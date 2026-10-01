"""RAGおよびVector Storeの抽象化と管理を担当するユースケースモジュール。

UI層とインフラ層の結合を疎にし、Vector StoreおよびStorageファイルの操作ロジックを提供します。
"""

from __future__ import annotations

from typing import Any

import structlog
from openai.types.vector_store import VectorStore

from src.infrastructure.openai_client import OpenAIClient

log = structlog.get_logger()


class RAGUseCase:
    """Vector Store および Storage 上のファイルを操作・管理するユースケースクラス。"""

    def __init__(self, client: OpenAIClient) -> None:
        """RAGUseCase を初期化します。

        Args:
            client: OpenAI インフラストラクチャクライアント
        """
        self.client = client

    async def list_vector_stores(self) -> list[VectorStore]:
        """登録されている全 Vector Store の一覧を取得します。"""
        return await self.client.list_vector_stores()

    async def create_vector_store(self, name: str) -> VectorStore:
        """指定した名称で新規 Vector Store を作成します。"""
        return await self.client.create_vector_store(name=name)

    async def update_vector_store_name(self, store_id: str, new_name: str) -> None:
        """Vector Store の名称を更新します。"""
        await self.client.update_vector_store(store_id, new_name)

    async def delete_vector_store(self, store_id: str) -> bool:
        """Vector Store を削除します。"""
        return await self.client.delete_vector_store(vector_store_id=store_id)

    async def list_files_in_store(self, store_id: str) -> list[dict[str, Any]]:
        """指定された Vector Store 内の全ファイルのメタデータを取得します。"""
        vs_files = await self.client.list_files_in_store(vector_store_id=store_id)
        file_details: list[dict[str, Any]] = []

        if vs_files:
            async with self.client._get_client() as ac:
                for vf in vs_files:
                    try:
                        f = await ac.files.retrieve(vf.id)
                        file_details.append(
                            {
                                "id": f.id,
                                "filename": f.filename,
                                "created_at": f.created_at,
                            }
                        )
                    except Exception as e:
                        log.warning("ファイルのメタデータの取得に失敗しました", file_id=vf.id, error=str(e))
                        continue
        return file_details

    async def upload_and_index_file(self, file_path: str, store_id: str) -> None:
        """ファイルをストレージにアップロードし、Vector Store へ関連付け（インデックス）します。"""
        f_obj = await self.client.upload_file(file_path=file_path)
        batch = await self.client.create_file_batch(vector_store_id=store_id, file_ids=[f_obj.id])
        await self.client.poll_batch_status(vector_store_id=store_id, batch_id=batch.id)

    async def delete_file_from_store_and_storage(self, store_id: str, file_id: str) -> None:
        """Vector Store からファイルのリンクを解除し、物理ストレージからも削除します。"""
        await self.client.delete_file_from_store(vector_store_id=store_id, file_id=file_id)
        await self.client.delete_file(file_id=file_id)
