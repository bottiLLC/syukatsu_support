"""
RAGおよびVector Storeの抽象化と管理を担当するUseCaseモジュール。
"""

import structlog
from typing import List, Any
from src.infrastructure.openai_client import OpenAIClient

log = structlog.get_logger()


class RAGUseCase:
    """
    Vector StoreおよびStorage上のファイルを操作・管理するためのビジネスロジック層。
    UIからの直接的なinfrastructure呼び出し（インフラ層への依存）を回避します。
    """
    def __init__(self, client: OpenAIClient):
        self.client = client

    async def list_vector_stores(self) -> List[Any]:
        return await self.client.list_vector_stores()

    async def create_vector_store(self, name: str) -> Any:
        return await self.client.create_vector_store(name=name)

    async def update_vector_store_name(self, store_id: str, new_name: str) -> None:
        """
        Vector Storeの名前を更新します。
        """
        await self.client.update_vector_store(store_id, new_name)

    async def delete_vector_store(self, store_id: str) -> bool:
        return await self.client.delete_vector_store(vector_store_id=store_id)

    async def list_files_in_store(self, store_id: str) -> List[dict]:
        """
        指定されたVector Store内のすべてのファイルのメタデータ（名前、日時、IDなど）を取得します。
        """
        vs_files = await self.client.list_files_in_store(vector_store_id=store_id)
        file_details = []
        
        if vs_files:
            async with self.client._get_client() as ac:
                for vf in vs_files:
                    try:
                        f = await ac.files.retrieve(vf.id)
                        file_details.append({
                            "id": f.id,
                            "filename": f.filename,
                            "created_at": f.created_at
                        })
                    except Exception as e:
                        log.warning("ファイルのメタデータの取得に失敗しました", file_id=vf.id, error=str(e))
                        continue
        return file_details

    async def upload_and_index_file(self, file_path: str, store_id: str) -> None:
        """
        ファイルをシステムにアップロードし、特定のVector Storeに関連付け（インデックス）ます。
        """
        # Storageへのアップロード
        f_obj = await self.client.upload_file(file_path=file_path)
        
        # Batchジョブを作成して、VectorStoreに所属させる
        batch = await self.client.create_file_batch(vector_store_id=store_id, file_ids=[f_obj.id])
        
        # 完了するまでポーリング待機
        await self.client.poll_batch_status(vector_store_id=store_id, batch_id=batch.id)

    async def delete_file_from_store_and_storage(self, store_id: str, file_id: str) -> None:
        """
        ファイルとStoreのリンクを解除し、Storageからも完全に削除します。
        """
        await self.client.delete_file_from_store(vector_store_id=store_id, file_id=file_id)
        await self.client.delete_file(file_id=file_id)
