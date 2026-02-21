"""
Unit tests for RAG services (FileService, VectorStoreService).
Focuses on Gemini API interactions for file and vector store management.
"""

from unittest.mock import AsyncMock, MagicMock, patch, mock_open
import pytest
from src.core.rag_services import FileService, VectorStoreService

# --- FileService Tests ---

class TestFileService:
    
    @pytest.fixture
    def service(self):
        with patch("src.core.base.genai.Client"):
            return FileService(api_key="test-key")

    @pytest.mark.asyncio
    async def test_upload_file_success(self, service):
        """Verify file upload calls correct API endpoint."""
        with patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.open", mock_open(read_data=b"data")):
            
            mock_client = AsyncMock()
            service.get_async_client = MagicMock(return_value=mock_client)
            mock_client.__aenter__.return_value = mock_client
            
            mock_file_obj = MagicMock()
            mock_file_obj.name = "file-123"
            mock_file_obj.display_name = "test.pdf"
            mock_client.aio.files.upload.return_value = mock_file_obj
            
            result = await service.upload_file("test.pdf")
            
            assert result.id == "file-123"
            mock_client.aio.files.upload.assert_called_once()
            
    @pytest.mark.asyncio
    async def test_upload_file_not_found(self, service):
        """Verify error when local file is missing."""
        with patch("pathlib.Path.exists", return_value=False):
            with pytest.raises(FileNotFoundError):
                await service.upload_file("non_existent.pdf")

    @pytest.mark.asyncio
    async def test_delete_file(self, service):
        """Verify file deletion."""
        mock_client = AsyncMock()
        service.get_async_client = MagicMock(return_value=mock_client)
        mock_client.__aenter__.return_value = mock_client
        
        success = await service.delete_file("file-123")
        assert success is True
        mock_client.aio.files.delete.assert_called_with(name="file-123")


# --- VectorStoreService Tests ---

class TestVectorStoreService:

    @pytest.fixture
    def service(self):
        return VectorStoreService(api_key="test-key")

    @pytest.mark.asyncio
    async def test_create_vector_store(self, service):
        """Verify creation of a vector store."""
        with patch("src.core.rag_services.db.create_store") as mock_create:
            mock_vs = MagicMock()
            mock_vs.id = "vs_abc"
            mock_create.return_value = mock_vs
            
            result = await service.create_vector_store("My Store")
            assert result.id == "vs_abc"
            mock_create.assert_called_with("My Store")

    @pytest.mark.asyncio
    async def test_poll_batch_status_success(self, service):
        """Verify polling logic returns completed immediately (mocked db behavior)."""
        status = await service.poll_batch_status("vs_1", "batch_1", interval=0.01)
        assert status == "completed"