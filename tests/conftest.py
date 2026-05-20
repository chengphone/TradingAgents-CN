"""
测试配置和公共 fixture
"""
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import jwt
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient as _TestClient


@pytest.fixture(autouse=True, scope="session")
def setup_test_env():
    os.environ.setdefault("DEBUG", "true")
    os.environ.setdefault("JWT_SECRET", "test-jwt-secret-for-testing-only-32chars")
    os.environ.setdefault("WECHAT_APPID", "test_appid")
    os.environ.setdefault("WECHAT_SECRET", "test_secret")
    os.environ.setdefault("WECHAT_DAILY_QUOTA", "10")
    os.environ.setdefault("CLOUDBASE_ENV_ID", "test-env")
    os.environ.setdefault("CLOUDBASE_API_TOKEN", "test-token")


class MockCloudBaseCollection:
    def __init__(self):
        self._data: Dict[str, Dict[str, Any]] = {}
        self._id_counter = 0

    def _generate_id(self) -> str:
        self._id_counter += 1
        return f"doc_{self._id_counter}"

    async def find_one(self, query: Optional[dict] = None) -> Optional[dict]:
        query = query or {}
        for doc_id, doc in self._data.items():
            if self._match_query(doc, query):
                return {**doc, "_id": doc_id}
        return None

    def find(self, query: Optional[dict] = None):
        return MockCursor(self, query or {})

    async def insert_one(self, document: dict):
        doc_id = self._generate_id()
        self._data[doc_id] = {**document, "_id": doc_id}
        return MockInsertResult(doc_id)

    async def update_one(self, query: dict, update: dict, upsert: bool = False):
        doc = await self.find_one(query)
        if doc:
            doc_id = doc["_id"]
            self._apply_update(self._data[doc_id], update)
            return MockUpdateResult(matched_count=1, modified_count=1)
        if upsert:
            new_doc = {}
            new_doc.update(query)
            if "$setOnInsert" in update:
                new_doc.update(update["$setOnInsert"])
            if "$set" in update:
                new_doc.update(update["$set"])
            doc_id = self._generate_id()
            self._data[doc_id] = {**new_doc, "_id": doc_id}
            return MockUpdateResult(matched_count=0, modified_count=1, upserted_id=doc_id)
        return MockUpdateResult(matched_count=0, modified_count=0)

    async def update_many(self, query: dict, update: dict):
        matched = modified = 0
        for doc_id, doc in list(self._data.items()):
            if self._match_query(doc, query):
                self._apply_update(self._data[doc_id], update)
                matched += 1
                modified += 1
        return MockUpdateResult(matched_count=matched, modified_count=modified)

    async def delete_one(self, query: dict):
        doc = await self.find_one(query)
        if doc:
            del self._data[doc["_id"]]
            return MockDeleteResult(deleted_count=1)
        return MockDeleteResult(deleted_count=0)

    async def count_documents(self, query: Optional[dict] = None) -> int:
        count = 0
        query = query or {}
        for doc in self._data.values():
            if self._match_query(doc, query):
                count += 1
        return count

    def _match_query(self, doc: dict, query: dict) -> bool:
        for key, value in query.items():
            if key == "$or":
                if not any(self._match_query(doc, cond) for cond in value):
                    return False
            elif key == "$and":
                if not all(self._match_query(doc, cond) for cond in value):
                    return False
            elif key not in doc:
                return False
            elif doc.get(key) != value:
                return False
        return True

    def _apply_update(self, doc: dict, update: dict):
        if "$set" in update:
            doc.update(update["$set"])
        if "$inc" in update:
            for key, delta in update["$inc"].items():
                doc[key] = doc.get(key, 0) + delta
        if "$unset" in update:
            for key in update["$unset"]:
                doc.pop(key, None)


class MockCursor:
    def __init__(self, collection: MockCloudBaseCollection, query: dict):
        self._collection = collection
        self._query = query
        self._sort_field = None
        self._sort_dir = 1
        self._limit = None
        self._skip = 0

    def sort(self, field: str, direction: int = 1):
        self._sort_field = field
        self._sort_dir = direction
        return self

    def limit(self, n: int):
        self._limit = n
        return self

    def skip(self, n: int):
        self._skip = n
        return self

    async def to_list(self, length: Optional[int] = None) -> list:
        results = []
        for doc_id, doc in self._collection._data.items():
            if self._collection._match_query(doc, self._query):
                results.append({**doc, "_id": doc_id})
        if self._sort_field:
            results.sort(key=lambda x: x.get(self._sort_field, ""), reverse=(self._sort_dir < 0))
        if self._skip:
            results = results[self._skip:]
        if self._limit:
            results = results[:self._limit]
        if length:
            results = results[:length]
        return results

    def __aiter__(self):
        self._results = None
        self._idx = 0
        return self

    async def __anext__(self):
        if self._results is None:
            self._results = await self.to_list()
        if self._idx >= len(self._results):
            raise StopAsyncIteration
        item = self._results[self._idx]
        self._idx += 1
        return item


class MockInsertResult:
    def __init__(self, inserted_id: str):
        self.inserted_id = inserted_id


class MockUpdateResult:
    def __init__(self, matched_count: int = 0, modified_count: int = 0, upserted_id: Optional[str] = None):
        self.matched_count = matched_count
        self.modified_count = modified_count
        self.upserted_id = upserted_id


class MockDeleteResult:
    def __init__(self, deleted_count: int = 0):
        self.deleted_count = deleted_count


class MockCloudBaseDatabase:
    def __init__(self):
        self._collections: Dict[str, MockCloudBaseCollection] = {}

    def __getitem__(self, name: str) -> MockCloudBaseCollection:
        if name not in self._collections:
            self._collections[name] = MockCloudBaseCollection()
        return self._collections[name]

    def __getattr__(self, name: str) -> MockCloudBaseCollection:
        return self[name]


@pytest.fixture
def mock_db() -> MockCloudBaseDatabase:
    return MockCloudBaseDatabase()


@pytest.fixture
def override_cloudbase(mock_db: MockCloudBaseDatabase):
    # Patch all locations where get_mongo_db is imported
    # Note: app.routers.analysis can't be imported due to langchain dependency
    # but the test file creates a mock router that imports inside the function
    with patch("app.core.cloudbase_client.get_mongo_db", return_value=mock_db), \
         patch("app.services.wechat_service.get_mongo_db", return_value=mock_db), \
         patch("app.routers.reports.get_mongo_db", return_value=mock_db):
        yield mock_db


@pytest.fixture
def user_a_token() -> str:
    payload = {
        "sub": "openid_a",
        "type": "wechat_miniprogram",
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, "test-jwt-secret-for-testing-only-32chars", algorithm="HS256")


@pytest.fixture
def user_b_token() -> str:
    payload = {
        "sub": "openid_b",
        "type": "wechat_miniprogram",
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, "test-jwt-secret-for-testing-only-32chars", algorithm="HS256")


@pytest.fixture
def expired_token() -> str:
    payload = {
        "sub": "openid_expired",
        "type": "wechat_miniprogram",
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        "iat": datetime.now(timezone.utc) - timedelta(hours=25),
    }
    return jwt.encode(payload, "test-jwt-secret-for-testing-only-32chars", algorithm="HS256")


@pytest.fixture
def auth_headers(user_a_token: str) -> dict:
    return {"Authorization": f"Bearer {user_a_token}"}


@pytest.fixture
def auth_headers_b(user_b_token: str) -> dict:
    return {"Authorization": f"Bearer {user_b_token}"}


@pytest.fixture
def health_app():
    from app.routers.health import router as health_router
    app = FastAPI()
    app.include_router(health_router, prefix="/api")
    return app


@pytest.fixture
def health_client(health_app):
    return _TestClient(health_app)


@pytest.fixture
def auth_app():
    from app.routers.wechat_auth import router as auth_router
    app = FastAPI()
    app.include_router(auth_router, prefix="/api/auth")
    return app


@pytest.fixture
def auth_client(auth_app):
    return _TestClient(auth_app)


@pytest.fixture
def reports_app():
    from app.routers.reports import router as reports_router
    app = FastAPI()
    app.include_router(reports_router, prefix="/api")
    return app


@pytest.fixture
def reports_client(reports_app):
    return _TestClient(reports_app)
