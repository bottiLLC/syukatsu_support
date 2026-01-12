"""
RAG (Retrieval-Augmented Generation) services module.

This module handles file uploads and Vector Store management for the RAG feature
in the Job Hunting Support Application. It adheres to the OpenAI API specifications.
"""

import logging
import time
from pathlib import Path
from typing import Any, List, Optional

from openai import NotFoundError
from openai.types import FileObject

from src.core.base import BaseOpenAIService

logger = logging.getLogger(__name__)


class FileService(BaseOpenAIService):
    """
    Service for managing files via the OpenAI API.

    Handles uploading, retrieving details, and deleting files.
    """

    def upload_file(self, file_path: str, purpose: str = "assistants") -> FileObject:
        """
        Uploads a file to OpenAI.

        Args:
            file_path (str): The local path to the file.
            purpose (str): The purpose of the file. Defaults to "assistants"
                           as required for Vector Stores.

        Returns:
            FileObject: The uploaded file object from the API.

        Raises:
            FileNotFoundError: If the local file does not exist.
            Exception: If the API call fails.
        """
        path_obj = Path(file_path)
        if not path_obj.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        logger.info(f"Uploading file: {file_path} (purpose={purpose})")
        try:
            with path_obj.open("rb") as f:
                response = self._client.files.create(file=f, purpose=purpose)
            logger.info(f"File uploaded successfully: {response.id}")
            return response
        except Exception as e:
            logger.error(f"Failed to upload file: {e}")
            raise

    def get_file_details(self, file_id: str) -> Optional[FileObject]:
        """
        Retrieves metadata for a specific file.

        Args:
            file_id (str): The ID of the file to retrieve.

        Returns:
            Optional[FileObject]: The file object if found, None otherwise.
        """
        try:
            return self._client.files.retrieve(file_id=file_id)
        except Exception as e:
            logger.error(f"Failed to retrieve file details for {file_id}: {e}")
            return None

    def delete_file(self, file_id: str) -> bool:
        """
        Deletes a file from OpenAI (permanent deletion).

        Args:
            file_id (str): The ID of the file to delete.

        Returns:
            bool: True if deletion was successful.
        """
        logger.info(f"Deleting file: {file_id}")
        try:
            response = self._client.files.delete(file_id=file_id)
            return response.deleted
        except Exception as e:
            logger.error(f"Failed to delete file {file_id}: {e}")
            raise


class VectorStoreService(BaseOpenAIService):
    """
    Service for managing Vector Stores and file batches using the OpenAI API.
    Accesses vector stores via the root namespace `client.vector_stores`.
    """

    def list_vector_stores(self, limit: int = 20) -> List[Any]:
        """
        Lists available vector stores.

        Args:
            limit (int): The maximum number of stores to return.

        Returns:
            List[Any]: A list of vector store objects.
        """
        try:
            response = self._client.vector_stores.list(limit=limit)
            return list(response.data)
        except Exception as e:
            logger.error(f"Failed to list vector stores: {e}")
            return []

    def create_vector_store(self, name: str) -> Any:
        """
        Creates a new vector store.

        Args:
            name (str): The name of the vector store.

        Returns:
            Any: The created vector store object.
        """
        logger.info(f"Creating vector store: {name}")
        try:
            return self._client.vector_stores.create(name=name)
        except Exception as e:
            logger.error(f"Failed to create vector store: {e}")
            raise

    def update_vector_store(self, vector_store_id: str, name: str) -> Any:
        """
        Updates a vector store's name.

        Args:
            vector_store_id (str): The ID of the vector store to update.
            name (str): The new name.

        Returns:
            Any: The updated vector store object.
        """
        logger.info(f"Updating vector store {vector_store_id} with name: {name}")
        try:
            return self._client.vector_stores.update(
                vector_store_id=vector_store_id, name=name
            )
        except Exception as e:
            logger.error(f"Failed to update vector store: {e}")
            raise

    def delete_vector_store(self, vector_store_id: str) -> bool:
        """
        Deletes a vector store.

        Args:
            vector_store_id (str): The ID of the vector store to delete.

        Returns:
            bool: True if deletion was successful.
        """
        logger.info(f"Deleting vector store: {vector_store_id}")
        try:
            response = self._client.vector_stores.delete(
                vector_store_id=vector_store_id
            )
            return response.deleted
        except Exception as e:
            logger.error(f"Failed to delete vector store: {e}")
            raise

    def create_file_batch(self, vector_store_id: str, file_ids: List[str]) -> Any:
        """
        Creates a file batch to add files to a vector store.

        Args:
            vector_store_id (str): The target vector store ID.
            file_ids (List[str]): List of file IDs to add.

        Returns:
            Any: The created batch object.
        """
        logger.info(
            f"Creating file batch for VS {vector_store_id} with {len(file_ids)} files."
        )
        try:
            return self._client.vector_stores.file_batches.create(
                vector_store_id=vector_store_id, file_ids=file_ids
            )
        except Exception as e:
            logger.error(f"Failed to create file batch: {e}")
            raise

    def poll_batch_status(
        self,
        vector_store_id: str,
        batch_id: str,
        interval: float = 2.0,
        max_retries: int = 60,
    ) -> str:
        """
        Polls the file batch status until completion or failure, or until timeout.

        Args:
            vector_store_id (str): The ID of the vector store.
            batch_id (str): The ID of the file batch.
            interval (float): Polling interval in seconds.
            max_retries (int): Maximum number of retries before timing out. Defaults to 60.

        Returns:
            str: The final status ('completed', 'failed', 'cancelled', or 'timed_out').
        """
        logger.info(f"Polling batch status: {batch_id}...")
        for _ in range(max_retries):
            try:
                batch = self._client.vector_stores.file_batches.retrieve(
                    vector_store_id=vector_store_id, batch_id=batch_id
                )
                status = batch.status

                if status in ["completed", "failed", "cancelled"]:
                    logger.info(f"Batch {batch_id} finished with status: {status}")
                    if status == "completed":
                        # Access file_counts safely
                        counts = getattr(batch, "file_counts", None)
                        logger.info(f"File counts: {counts}")
                    return status

                time.sleep(interval)
            except Exception as e:
                logger.error(f"Error polling batch status: {e}")
                # Continue polling even if a temporary error occurs
                pass

        logger.error(f"Polling timed out for batch {batch_id}")
        return "timed_out"

    def list_files_in_store(self, vector_store_id: str) -> List[Any]:
        """
        Lists files currently in the vector store.

        Args:
            vector_store_id (str): The vector store ID.

        Returns:
            List[Any]: List of file objects in the store.
        """
        try:
            response = self._client.vector_stores.files.list(
                vector_store_id=vector_store_id
            )
            return list(response.data)
        except NotFoundError:
            return []
        except Exception as e:
            logger.error(f"Failed to list files in store {vector_store_id}: {e}")
            return []

    def delete_file_from_store(self, vector_store_id: str, file_id: str) -> bool:
        """
        Removes a file from the vector store (does not delete the actual file entity).

        Args:
            vector_store_id (str): The vector store ID.
            file_id (str): The ID of the file to remove.

        Returns:
            bool: True if successful.
        """
        logger.info(f"Removing file {file_id} from store {vector_store_id}")
        try:
            response = self._client.vector_stores.files.delete(
                vector_store_id=vector_store_id, file_id=file_id
            )
            return response.deleted
        except Exception as e:
            logger.error(f"Failed to remove file from store: {e}")
            raise