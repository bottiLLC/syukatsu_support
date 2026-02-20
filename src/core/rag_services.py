"""
RAG (Retrieval-Augmented Generation) services module.

This module handles file uploads and Vector Store management for the RAG feature
in the Job Hunting Support Application. It adheres to the OpenAI API specifications
using AsyncOpenAI context managers.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, List, Optional

from openai import NotFoundError
from openai.types import FileObject

from src.core.base import BaseOpenAIService

logger = logging.getLogger(__name__)


class FileService(BaseOpenAIService):
    """
    Service for managing files via the OpenAI API.

    Handles uploading, retrieving details, and deleting files asynchronously.
    """

    async def upload_file(self, file_path: str, purpose: str = "assistants") -> FileObject:
        """
        Uploads a file to OpenAI asynchronously.

        Args:
            file_path (str): The local path to the file.
            purpose (str): The purpose of the file. Defaults to "assistants".

        Returns:
            FileObject: The uploaded file object from the API.

        Raises:
            FileNotFoundError: If the local file does not exist.
            Exception: If the API call fails.
        """
        path_obj = Path(file_path)
        if not path_obj.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        logger.info(f"Uploading file async: {file_path} (purpose={purpose})")
        try:
            async with self.get_async_client() as client:
                with path_obj.open("rb") as f:
                    response = await client.files.create(file=f, purpose=purpose)
                logger.info(f"File uploaded successfully: {response.id}")
                return response
        except Exception as e:
            logger.error(f"Failed to upload file: {e}")
            raise

    async def get_file_details(self, file_id: str) -> Optional[FileObject]:
        """
        Retrieves metadata for a specific file asynchronously.
        """
        try:
            async with self.get_async_client() as client:
                return await client.files.retrieve(file_id=file_id)
        except Exception as e:
            logger.error(f"Failed to retrieve file details for {file_id}: {e}")
            return None

    async def delete_file(self, file_id: str) -> bool:
        """
        Deletes a file from OpenAI asynchronously (permanent deletion).
        """
        logger.info(f"Deleting file async: {file_id}")
        try:
            async with self.get_async_client() as client:
                response = await client.files.delete(file_id=file_id)
                return response.deleted
        except Exception as e:
            logger.error(f"Failed to delete file {file_id}: {e}")
            raise


class VectorStoreService(BaseOpenAIService):
    """
    Service for managing Vector Stores and file batches using the Async OpenAI API.
    """

    async def list_vector_stores(self, limit: int = 20) -> List[Any]:
        """
        Lists available vector stores asynchronously.
        """
        try:
            async with self.get_async_client() as client:
                response = await client.vector_stores.list(limit=limit)
                return list(response.data)
        except Exception as e:
            logger.error(f"Failed to list vector stores: {e}")
            return []

    async def create_vector_store(self, name: str) -> Any:
        """
        Creates a new vector store asynchronously.
        """
        logger.info(f"Creating vector store async: {name}")
        try:
            async with self.get_async_client() as client:
                return await client.vector_stores.create(name=name)
        except Exception as e:
            logger.error(f"Failed to create vector store: {e}")
            raise

    async def update_vector_store(self, vector_store_id: str, name: str) -> Any:
        """
        Updates a vector store's name asynchronously.
        """
        logger.info(f"Updating vector store {vector_store_id} with name: {name}")
        try:
            async with self.get_async_client() as client:
                return await client.vector_stores.update(
                    vector_store_id=vector_store_id, name=name
                )
        except Exception as e:
            logger.error(f"Failed to update vector store: {e}")
            raise

    async def delete_vector_store(self, vector_store_id: str) -> bool:
        """
        Deletes a vector store asynchronously.
        """
        logger.info(f"Deleting vector store async: {vector_store_id}")
        try:
            async with self.get_async_client() as client:
                response = await client.vector_stores.delete(
                    vector_store_id=vector_store_id
                )
                return response.deleted
        except Exception as e:
            logger.error(f"Failed to delete vector store: {e}")
            raise

    async def create_file_batch(self, vector_store_id: str, file_ids: List[str]) -> Any:
        """
        Creates an asynchronous file batch to add files to a vector store.
        """
        logger.info(
            f"Creating async file batch for VS {vector_store_id} with {len(file_ids)} files."
        )
        try:
            async with self.get_async_client() as client:
                return await client.vector_stores.file_batches.create(
                    vector_store_id=vector_store_id, file_ids=file_ids
                )
        except Exception as e:
            logger.error(f"Failed to create file batch: {e}")
            raise

    async def poll_batch_status(
        self,
        vector_store_id: str,
        batch_id: str,
        interval: float = 2.0,
        max_retries: int = 60,
    ) -> str:
        """
        Polls the file batch status asynchronously until completion, failure, or timeout.
        """
        logger.info(f"Polling async batch status: {batch_id}...")
        for _ in range(max_retries):
            try:
                async with self.get_async_client() as client:
                    batch = await client.vector_stores.file_batches.retrieve(
                        vector_store_id=vector_store_id, batch_id=batch_id
                    )
                    status = batch.status

                    if status in ["completed", "failed", "cancelled"]:
                        logger.info(f"Batch {batch_id} finished with status: {status}")
                        if status == "completed":
                            counts = getattr(batch, "file_counts", None)
                            logger.info(f"File counts: {counts}")
                        return status

                await asyncio.sleep(interval)
            except Exception as e:
                logger.error(f"Error polling batch status: {e}")
                await asyncio.sleep(interval)

        logger.error(f"Polling timed out for batch {batch_id}")
        return "timed_out"

    async def list_files_in_store(self, vector_store_id: str) -> List[Any]:
        """
        Lists files currently in the vector store asynchronously.
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
            logger.error(f"Failed to list files in store {vector_store_id}: {e}")
            return []

    async def delete_file_from_store(self, vector_store_id: str, file_id: str) -> bool:
        """
        Removes a file from the vector store asynchronously.
        """
        logger.info(f"Removing file {file_id} from store {vector_store_id}")
        try:
            async with self.get_async_client() as client:
                response = await client.vector_stores.files.delete(
                    vector_store_id=vector_store_id, file_id=file_id
                )
                return response.deleted
        except Exception as e:
            logger.error(f"Failed to remove file from store: {e}")
            raise