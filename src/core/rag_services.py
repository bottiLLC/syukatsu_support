"""
RAG (Retrieval-Augmented Generation) services module.

This module simulates OpenAI's Vector Store management for the RAG feature
using a local JSON database and Gemini's File API for actual file uploads.
"""

import asyncio
import json
import logging
import uuid
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, List, Optional

from google.genai import errors as genai_errors
from google.genai import types as genai_types

from src.core.base import BaseGeminiService

logger = logging.getLogger(__name__)

# --- Local DB for Vector Store Simulation ---
DB_DIR = Path("data")
DB_FILE = DB_DIR / "vector_stores.json"

class _VectorStoreDB:
    def __init__(self):
        DB_DIR.mkdir(exist_ok=True, parents=True)
        if not DB_FILE.exists():
            self._save({"stores": {}})

    def _load(self):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read local DB: {e}")
            return {"stores": {}}

    def _save(self, data):
        try:
            with open(DB_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to write to local DB: {e}")

    def list_stores(self):
        data = self._load()
        stores = []
        for sid, sdata in data.get("stores", {}).items():
            stores.append(SimpleNamespace(
                id=sid,
                name=sdata.get("name", ""),
                status="completed",
                usage_bytes=0,
                file_counts=SimpleNamespace(total=len(sdata.get("files", [])))
            ))
        return stores

    def create_store(self, name):
        data = self._load()
        sid = f"vs_{uuid.uuid4().hex[:16]}"
        data.setdefault("stores", {})[sid] = {"name": name, "files": []}
        self._save(data)
        return SimpleNamespace(id=sid, name=name, status="completed", usage_bytes=0, file_counts=SimpleNamespace(total=0))

    def update_store(self, sid, name):
        data = self._load()
        if sid in data.get("stores", {}):
            data["stores"][sid]["name"] = name
            self._save(data)
        return SimpleNamespace(id=sid, name=name, status="completed", usage_bytes=0, file_counts=SimpleNamespace(total=len(data.get("stores",{}).get(sid,{}).get("files",[]))))

    def delete_store(self, sid):
        data = self._load()
        if sid in data.get("stores", {}):
            del data["stores"][sid]
            self._save(data)
        return True

    def add_files(self, sid, file_ids):
        data = self._load()
        if sid in data.get("stores", {}):
            current = set(data["stores"][sid].get("files", []))
            for fid in file_ids:
                if fid not in current:
                    data["stores"][sid].setdefault("files", []).append(fid)
            self._save(data)

    def remove_file(self, sid, file_id):
        data = self._load()
        if sid in data.get("stores", {}):
            files = data["stores"][sid].get("files", [])
            if file_id in files:
                files.remove(file_id)
                self._save(data)

    def get_files(self, sid):
        data = self._load()
        return data.get("stores", {}).get(sid, {}).get("files", [])


db = _VectorStoreDB()

def _gemini_file_to_namespace(file_obj) -> SimpleNamespace:
    # Convert Gemini's File object to a SimpleNamespace that matches the UI expectations
    return SimpleNamespace(
        id=file_obj.name,
        filename=file_obj.display_name or str(file_obj.uri),
        created_at=int(time.time()), 
    )

class FileService(BaseGeminiService):
    """
    Service for managing files via the Gemini API.
    Handles uploading, retrieving details, and deleting files asynchronously.
    """

    async def upload_file(self, file_path: str, purpose: str = "assistants") -> Any:
        path_obj = Path(file_path)
        if not path_obj.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        logger.info(f"Uploading file async to Gemini: {file_path}")
        try:
            async with self.get_async_client() as client:
                # Use standard client for file upload or asyncio to_thread if aio missing
                # We'll use client.files.upload since files api is often synchronous or basic
                try: 
                    response = await client.aio.files.upload(file=str(path_obj), config={'display_name': path_obj.name})
                except AttributeError:
                    import asyncio
                    response = await asyncio.to_thread(
                        client.files.upload, file=str(path_obj), config={'display_name': path_obj.name}
                    )
                logger.info(f"File uploaded successfully: {response.name}")
                return _gemini_file_to_namespace(response)
        except Exception as e:
            logger.error(f"Failed to upload file: {e}")
            raise

    async def get_file_details(self, file_id: str) -> Optional[Any]:
        try:
            async with self.get_async_client() as client:
                try:
                    response = await client.aio.files.get(name=file_id)
                except AttributeError:
                    import asyncio
                    response = await asyncio.to_thread(client.files.get, name=file_id)
                return _gemini_file_to_namespace(response)
        except Exception as e:
            logger.error(f"Failed to retrieve file details for {file_id}: {e}")
            return None

    async def delete_file(self, file_id: str) -> bool:
        logger.info(f"Deleting file async from Gemini: {file_id}")
        try:
            async with self.get_async_client() as client:
                try:
                    await client.aio.files.delete(name=file_id)
                except AttributeError:
                    import asyncio
                    await asyncio.to_thread(client.files.delete, name=file_id)
                return True
        except Exception as e:
            logger.error(f"Failed to delete file {file_id}: {e}")
            raise


class VectorStoreService(BaseGeminiService):
    """
    Simulates Gemini API Vector Stores using a local database.
    """

    async def list_vector_stores(self, limit: int = 20) -> List[Any]:
        return db.list_stores()

    async def create_vector_store(self, name: str) -> Any:
        return db.create_store(name)

    async def update_vector_store(self, vector_store_id: str, name: str) -> Any:
        return db.update_store(vector_store_id, name)

    async def delete_vector_store(self, vector_store_id: str) -> bool:
        return db.delete_store(vector_store_id)

    async def create_file_batch(self, vector_store_id: str, file_ids: List[str]) -> Any:
        logger.info(f"Adding {len(file_ids)} files to store {vector_store_id}")
        db.add_files(vector_store_id, file_ids)
        return SimpleNamespace(id="batch_mock", status="completed", file_counts=SimpleNamespace(completed=len(file_ids), total=len(file_ids)))

    async def poll_batch_status(
        self,
        vector_store_id: str,
        batch_id: str,
        interval: float = 2.0,
        max_retries: int = 60,
    ) -> str:
        await asyncio.sleep(0.1)
        return "completed"

    async def list_files_in_store(self, vector_store_id: str) -> List[Any]:
        fids = db.get_files(vector_store_id)
        return [SimpleNamespace(id=fid, created_at=int(time.time())) for fid in fids]

    async def delete_file_from_store(self, vector_store_id: str, file_id: str) -> bool:
        db.remove_file(vector_store_id, file_id)
        return True