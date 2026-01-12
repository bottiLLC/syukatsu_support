"""
Unit tests for RAG services (FileService, VectorStoreService).
Focuses on OpenAI API interactions for file and vector store management.
"""

from unittest.mock import MagicMock, patch, mock_open
import pytest
from src.core.rag_services import FileService, VectorStoreService

# --- FileService Tests ---

class TestFileService:
    
    @pytest.fixture
    def service(self):
        with patch("src.core.base.OpenAI"):
            return FileService(api_key="test-key")

    def test_upload_file_success(self, service):
        """Verify file upload calls correct API endpoint."""
        # Mock file system
        with patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.open", mock_open(read_data=b"data")):
            
            # Mock API response
            mock_file_obj = MagicMock()
            mock_file_obj.id = "file-123"
            service._client.files.create.return_value = mock_file_obj
            
            result = service.upload_file("test.pdf")
            
            assert result.id == "file-123"
            service._client.files.create.assert_called_once()
            
    def test_upload_file_not_found(self, service):
        """Verify error when local file is missing."""
        with patch("pathlib.Path.exists", return_value=False):
            with pytest.raises(FileNotFoundError):
                service.upload_file("non_existent.pdf")

    def test_delete_file(self, service):
        """Verify file deletion."""
        mock_resp = MagicMock()
        mock_resp.deleted = True
        service._client.files.delete.return_value = mock_resp
        
        success = service.delete_file("file-123")
        assert success is True
        service._client.files.delete.assert_called_with(file_id="file-123")


# --- VectorStoreService Tests ---

class TestVectorStoreService:

    @pytest.fixture
    def service(self):
        with patch("src.core.base.OpenAI"):
            return VectorStoreService(api_key="test-key")

    def test_create_vector_store(self, service):
        """Verify creation of a vector store."""
        mock_vs = MagicMock()
        mock_vs.id = "vs_abc"
        service._client.vector_stores.create.return_value = mock_vs
        
        result = service.create_vector_store("My Store")
        assert result.id == "vs_abc"
        service._client.vector_stores.create.assert_called_with(name="My Store")

    def test_poll_batch_status_success(self, service):
        """Verify polling logic stops when status is completed."""
        # Mock retrieve to return 'in_progress' then 'completed'
        mock_batch_progress = MagicMock()
        mock_batch_progress.status = "in_progress"
        
        mock_batch_done = MagicMock()
        mock_batch_done.status = "completed"
        mock_batch_done.file_counts = {"total": 1}
        
        service._client.vector_stores.file_batches.retrieve.side_effect = [
            mock_batch_progress,
            mock_batch_done
        ]
        
        # Set short interval for test speed
        status = service.poll_batch_status("vs_1", "batch_1", interval=0.01)
        
        assert status == "completed"
        assert service._client.vector_stores.file_batches.retrieve.call_count == 2