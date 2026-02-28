"""
Unit tests for RAG services (FileService, VectorStoreService).
Focuses on OpenAI API interactions for file and vector store management.
"""

from unittest.mock import AsyncMock, patch, mock_open, MagicMock
import pytest
import io
from src.core.rag_services import FileService, VectorStoreService

pytestmark = pytest.mark.asyncio

@pytest.fixture
def mock_client():
    client = AsyncMock()
    return client

@pytest.fixture
def mock_base_service(mock_client):
    from contextlib import asynccontextmanager
    @asynccontextmanager
    async def get_async_client(self, *args, **kwargs):
        yield mock_client
        
    with patch("src.core.base.BaseOpenAIService.get_async_client", get_async_client):
        yield mock_client

class TestFileService:
    @pytest.fixture
    def service(self):
        return FileService(api_key="test-key")

    async def test_upload_file_success(self, service, mock_base_service):
        mock_client = mock_base_service
        # OpenAI SDK expects IOBase or bytes for file uploads in tests
        file_content = io.BytesIO(b"data")
        
        with patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.open", return_value=file_content):
            
            mock_file_obj = AsyncMock()
            mock_file_obj.id = "file-123"
            mock_client.files.create.return_value = mock_file_obj
            
            result = await service.upload_file("test.pdf")
            assert result.id == "file-123"
            mock_client.files.create.assert_called_once()
            
    async def test_upload_file_not_found(self, service, mock_base_service):
        with patch("pathlib.Path.exists", return_value=False):
            with pytest.raises(FileNotFoundError):
                await service.upload_file("non_existent.pdf")

    async def test_delete_file(self, service, mock_base_service):
        mock_client = mock_base_service
        mock_resp = AsyncMock()
        mock_resp.deleted = True
        mock_client.files.delete.return_value = mock_resp
        
        success = await service.delete_file("file-123")
        assert success is True
        mock_client.files.delete.assert_called_with(file_id="file-123")

class TestVectorStoreService:
    @pytest.fixture
    def service(self):
        return VectorStoreService(api_key="test-key")

    async def test_create_vector_store(self, service, mock_base_service):
        mock_client = mock_base_service
        mock_vs = AsyncMock()
        mock_vs.id = "vs_abc"
        mock_client.vector_stores.create.return_value = mock_vs
        
        result = await service.create_vector_store("My Store")
        assert result.id == "vs_abc"
        mock_client.vector_stores.create.assert_called_with(name="My Store")

    async def test_poll_batch_status_success(self, service, mock_base_service):
        mock_client = mock_base_service
        mock_batch_progress = AsyncMock()
        mock_batch_progress.status = "in_progress"
        
        mock_batch_done = AsyncMock()
        mock_batch_done.status = "completed"
        mock_batch_done.file_counts = {"total": 1}
        
        # AsyncMock side_effects need to be awaited instances if they are returned by coroutines.
        # But for retrieve, it's just an async def returning an object.
        mock_client.vector_stores.file_batches.retrieve.side_effect = [
            mock_batch_progress,
            mock_batch_done
        ]
        
        status = await service.poll_batch_status("vs_1", "batch_1", interval=0.01)
        assert status == "completed"
        assert mock_client.vector_stores.file_batches.retrieve.call_count == 2