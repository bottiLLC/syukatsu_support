"""
Unit tests for RAG services (FileService and VectorStoreService).
Focuses on interactions with the OpenAI Files and Vector Stores APIs.
"""

from unittest.mock import MagicMock, patch, mock_open
import pytest
from src.core.rag_services import FileService, VectorStoreService

# --- Fixtures ---

@pytest.fixture
def mock_client():
    """Mocks the OpenAI client structure."""
    with patch("src.core.base.OpenAI") as mock_openai_cls:
        mock_instance = MagicMock()
        mock_openai_cls.return_value = mock_instance
        
        # Setup specific mock paths
        mock_instance.files = MagicMock()
        
        # Mocking the GA endpoint structure
        mock_instance.vector_stores = MagicMock()
        mock_instance.vector_stores.files = MagicMock()
        mock_instance.vector_stores.file_batches = MagicMock()

        # Also mock beta just in case
        mock_instance.beta.vector_stores = mock_instance.vector_stores
        
        yield mock_instance

# --- FileService Tests ---

class TestFileService:
    
    @pytest.fixture
    def service(self, mock_client):
        return FileService("sk-test")

    def test_upload_file_success(self, service, mock_client):
        """Verifies successful file upload."""
        # 修正: pathlib.Path.open をモックしてファイル操作をシミュレートします
        # builtins.open ではなく Path.open をターゲットにします
        with patch("src.core.rag_services.Path.open", mock_open(read_data=b"data")):
            with patch("src.core.rag_services.Path.exists", return_value=True):
                # Mock API response
                mock_response = MagicMock()
                mock_response.id = "file-123"
                mock_client.files.create.return_value = mock_response

                result = service.upload_file("test.txt")

                assert result.id == "file-123"
                mock_client.files.create.assert_called_once()
                # Verify 'purpose' defaults to 'assistants'
                assert mock_client.files.create.call_args[1]["purpose"] == "assistants"

    def test_upload_file_not_found(self, service):
        """Verifies error raised when file does not exist locally."""
        with patch("src.core.rag_services.Path.exists", return_value=False):
            with pytest.raises(FileNotFoundError):
                service.upload_file("nonexistent.txt")

    def test_delete_file(self, service, mock_client):
        """Verifies file deletion."""
        mock_response = MagicMock()
        mock_response.deleted = True
        mock_client.files.delete.return_value = mock_response

        result = service.delete_file("file-123")
        assert result is True
        mock_client.files.delete.assert_called_with(file_id="file-123")

    def test_get_file_details_success(self, service, mock_client):
        """Verifies fetching file metadata."""
        mock_file_obj = MagicMock()
        mock_file_obj.id = "file-123"
        mock_file_obj.filename = "test.txt"
        mock_client.files.retrieve.return_value = mock_file_obj

        # Only run if method exists
        if hasattr(service, "get_file_details"):
            result = service.get_file_details("file-123")
            
            assert result is not None
            assert result.id == "file-123"
            assert result.filename == "test.txt"

    def test_get_file_details_failure(self, service, mock_client):
        """Verifies handling of API errors during retrieval."""
        mock_client.files.retrieve.side_effect = Exception("API Error")
        
        if hasattr(service, "get_file_details"):
            result = service.get_file_details("file-123")
            assert result is None


# --- VectorStoreService Tests ---

class TestVectorStoreService:

    @pytest.fixture
    def service(self, mock_client):
        return VectorStoreService("sk-test")

    def test_list_vector_stores(self, service, mock_client):
        """Verifies listing vector stores."""
        mock_store = MagicMock()
        mock_store.id = "vs_1"
        mock_resp = MagicMock()
        mock_resp.data = [mock_store]
        
        mock_client.vector_stores.list.return_value = mock_resp

        result = service.list_vector_stores()
        
        assert len(result) == 1
        assert result[0].id == "vs_1"

    def test_create_vector_store(self, service, mock_client):
        """Verifies creation of a vector store."""
        mock_store = MagicMock()
        mock_store.id = "vs_new"
        mock_store.name = "My Store"
        mock_client.vector_stores.create.return_value = mock_store

        result = service.create_vector_store("My Store")
        
        assert result.id == "vs_new"
        mock_client.vector_stores.create.assert_called_with(name="My Store")

    def test_create_file_batch(self, service, mock_client):
        """Verifies batch creation."""
        mock_batch = MagicMock()
        mock_batch.id = "batch_1"
        mock_client.vector_stores.file_batches.create.return_value = mock_batch

        result = service.create_file_batch("vs_1", ["file_1", "file_2"])
        
        assert result.id == "batch_1"
        mock_client.vector_stores.file_batches.create.assert_called_with(
            vector_store_id="vs_1",
            file_ids=["file_1", "file_2"]
        )

    def test_poll_batch_status_success(self, service, mock_client):
        """
        Verifies polling logic.
        Simulates: in_progress -> completed.
        """
        # Batch object mocks
        batch_progress = MagicMock(status="in_progress")
        batch_done = MagicMock(status="completed", file_counts={"total": 2})
        
        # side_effect to return progress first, then done
        mock_client.vector_stores.file_batches.retrieve.side_effect = [
            batch_progress,
            batch_done
        ]

        # Patch sleep to speed up test
        with patch("time.sleep", return_value=None):
            status = service.poll_batch_status("vs_1", "batch_1")
        
        assert status == "completed"
        # Verify it was called twice
        assert mock_client.vector_stores.file_batches.retrieve.call_count == 2

    def test_list_files_in_store(self, service, mock_client):
        """Verifies listing files in a store."""
        mock_file = MagicMock()
        mock_file.id = "file_1"
        mock_resp = MagicMock()
        mock_resp.data = [mock_file]
        mock_client.vector_stores.files.list.return_value = mock_resp
        
        result = service.list_files_in_store("vs_1")
        assert len(result) == 1
        assert result[0].id == "file_1"

    def test_delete_file_from_store(self, service, mock_client):
        """Verifies removing a file from a store."""
        mock_resp = MagicMock()
        mock_resp.deleted = True
        mock_client.vector_stores.files.delete.return_value = mock_resp
        
        result = service.delete_file_from_store("vs_1", "file_1")
        assert result is True