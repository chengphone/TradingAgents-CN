"""
CloudBase (云开发) 云数据库 HTTP API 客户端
替代 MongoDB/Motor + Redis，提供对等的异步 CRUD 接口
"""

import logging
import os
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)


class CloudBaseConfig:
    """从环境变量加载云开发配置"""

    @property
    def env_id(self) -> str:
        return os.getenv("CLOUDBASE_ENV_ID", "")

    @property
    def api_token(self) -> str:
        return os.getenv("CLOUDBASE_API_TOKEN", "") or os.getenv("CLOUDBASE_API_KEY", "")

    @property
    def base_url(self) -> str:
        return os.getenv(
            "CLOUDBASE_BASE_URL",
            f"https://{self.env_id}.api.tcloudbasegateway.com",
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.env_id and self.api_token)


cloudbase_config = CloudBaseConfig()


class CloudBaseCursor:
    """模拟 MongoDB cursor，支持 sort / limit / 异步迭代"""

    def __init__(self, collection: "CloudBaseCollection", query: dict):
        self._collection = collection
        self._query = query
        self._sort_field: Optional[str] = None
        self._sort_dir: str = "asc"
        self._limit_val: Optional[int] = None

    def sort(self, field: str, direction: int = 1):
        self._sort_field = field
        self._sort_dir = "asc" if direction >= 0 else "desc"
        return self

    def limit(self, n: int):
        self._limit_val = n
        return self

    async def to_list(self, length: Optional[int] = None) -> list:
        """获取所有结果"""
        limit = length or self._limit_val or 100
        order = None
        if self._sort_field:
            order = [{"field": self._sort_field, "direction": self._sort_dir}]
        result = await self._collection._query_documents(
            query=self._query, limit=limit, order=order
        )
        return result

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


class CloudBaseCollection:
    """代表云数据库中的一个集合，提供与 Motor collection 对等的接口"""

    def __init__(self, client: "CloudBaseClient", name: str):
        self._client = client
        self.name = name

    async def find_one(self, query: Optional[dict] = None, sort: Optional[list] = None) -> Optional[dict]:
        """查找单个文档"""
        order = None
        if sort:
            order = [{"field": s[0], "direction": "asc" if s[1] >= 0 else "desc"} for s in sort]
        results = await self._query_documents(query=query or {}, limit=1, order=order)
        return results[0] if results else None

    def find(self, query: Optional[dict] = None) -> CloudBaseCursor:
        """返回 cursor，支持 .sort().limit() 链式调用"""
        return CloudBaseCursor(self, query or {})

    async def insert_one(self, document: dict) -> "InsertOneResult":
        """插入单个文档"""
        url = f"{self._client._db_url}/{self.name}/documents/insert"
        body = {"documents": [document]}
        resp = await self._client._request("POST", url, json=body)
        data = resp
        doc_id = ""
        inserted_ids = data.get("inserted_ids", [])
        if inserted_ids:
            doc_id = inserted_ids[0]
        return InsertOneResult(inserted_id=doc_id)

    async def update_one(self, query: dict, update: dict, upsert: bool = False) -> "UpdateResult":
        """更新单个文档，支持 upsert 和 MongoDB 更新操作符

        Args:
            query: 查询条件
            update: 更新操作，支持 $set, $setOnInsert, $inc, $unset
            upsert: 如果文档不存在是否插入新文档
        """
        doc = await self.find_one(query)

        if doc:
            doc_id = doc["_id"]
            patch_data = {}

            # 处理 $set
            if "$set" in update:
                patch_data.update(update["$set"])

            # 处理 $inc - 对现有文档的数值字段进行增量操作
            if "$inc" in update:
                for key, delta in update["$inc"].items():
                    current_val = doc.get(key, 0)
                    if isinstance(current_val, (int, float)):
                        patch_data[key] = current_val + delta
                    else:
                        patch_data[key] = delta

            # 处理 $unset
            if "$unset" in update:
                for key in update["$unset"]:
                    patch_data[key] = None

            url = f"{self._client._db_url}/{self.name}/documents/{doc_id}"
            body = {"data": patch_data}
            await self._client._request("PATCH", url, json=body)

            return UpdateResult(matched_count=1, modified_count=1)

        # 文档不存在时的处理
        if upsert:
            # 构造新文档：先从查询条件提取字段，再应用更新操作符
            insert_doc = {}
            insert_doc.update(query)

            # $setOnInsert 仅在插入时应用
            if "$setOnInsert" in update:
                insert_doc.update(update["$setOnInsert"])

            # $set 在插入时也应用
            if "$set" in update:
                insert_doc.update(update["$set"])

            # 插入新文档
            result = await self.insert_one(insert_doc)
            return UpdateResult(matched_count=0, modified_count=1, upserted_id=result.inserted_id)

        return UpdateResult(matched_count=0, modified_count=0)

    async def update_many(self, query: dict, update: dict) -> "UpdateResult":
        """更新多个文档（先查后逐个更新）

        注意：CloudBase API 不支持批量更新，需要逐个处理
        """
        matched_count = 0
        modified_count = 0

        # 查询所有匹配的文档
        cursor = self.find(query)
        docs = await cursor.to_list(1000)  # 最多处理 1000 个文档

        for doc in docs:
            doc_id = doc["_id"]
            patch_data = {}

            # 处理 $set
            if "$set" in update:
                patch_data.update(update["$set"])

            # 处理 $inc
            if "$inc" in update:
                for key, delta in update["$inc"].items():
                    current_val = doc.get(key, 0)
                    if isinstance(current_val, (int, float)):
                        patch_data[key] = current_val + delta
                    else:
                        patch_data[key] = delta

            # 处理 $unset
            if "$unset" in update:
                for key in update["$unset"]:
                    patch_data[key] = None

            if patch_data:
                url = f"{self._client._db_url}/{self.name}/documents/{doc_id}"
                await self._client._request("PATCH", url, json={"data": patch_data})
                modified_count += 1

            matched_count += 1

        return UpdateResult(matched_count=matched_count, modified_count=modified_count)

    async def delete_one(self, query: dict) -> "DeleteResult":
        """删除单个文档。先查后删"""
        doc = await self.find_one(query)
        if not doc:
            return DeleteResult(deleted_count=0)
        doc_id = doc["_id"]
        url = f"{self._client._db_url}/{self.name}/documents/{doc_id}"
        await self._client._request("DELETE", url)
        return DeleteResult(deleted_count=1)

    async def count_documents(self, query: Optional[dict] = None) -> int:
        """统计文档数量"""
        results = await self._query_documents(query=query or {}, limit=1000, count_only=True)
        return len(results)

    async def replace_one(
        self, query: dict, replacement: dict, upsert: bool = False
    ) -> "UpdateResult":
        """替换文档（upsert 支持）"""
        doc = await self.find_one(query)
        if doc:
            doc_id = doc["_id"]
            url = f"{self._client._db_url}/{self.name}/documents/{doc_id}"
            await self._client._request("PATCH", url, json={"data": replacement})
            return UpdateResult(matched_count=1, modified_count=1)
        elif upsert:
            result = await self.insert_one(replacement)
            return UpdateResult(
                matched_count=0, modified_count=1, upserted_id=result.inserted_id
            )
        return UpdateResult(matched_count=0, modified_count=0)

    async def _query_documents(
        self,
        query: dict,
        limit: int = 100,
        offset: int = 0,
        order: Optional[List[dict]] = None,
        count_only: bool = False,
    ) -> list:
        """底层 HTTP 查询"""
        url = f"{self._client._db_url}/{self.name}/documents"
        body: Dict[str, Any] = {"query": query, "limit": limit, "offset": offset}
        if order:
            body["order"] = order
        resp = await self._client._request("POST", url, json=body)
        if isinstance(resp, dict):
            return resp.get("documents", []) or resp.get("data", []) or []
        return []


class InsertOneResult:
    def __init__(self, inserted_id: str):
        self.inserted_id = inserted_id


class UpdateResult:
    def __init__(
        self,
        matched_count: int = 0,
        modified_count: int = 0,
        upserted_id: Optional[str] = None,
    ):
        self.matched_count = matched_count
        self.modified_count = modified_count
        self.upserted_id = upserted_id


class DeleteResult:
    def __init__(self, deleted_count: int = 0):
        self.deleted_count = deleted_count


class CloudBaseDatabase:
    """云数据库实例，通过属性访问集合"""

    def __init__(self, client: "CloudBaseClient"):
        self._client = client
        self._collections: Dict[str, CloudBaseCollection] = {}

    def __getattr__(self, name: str) -> CloudBaseCollection:
        if name.startswith("_"):
            raise AttributeError(name)
        return self[name]

    def __getitem__(self, name: str) -> CloudBaseCollection:
        if name not in self._collections:
            self._collections[name] = CloudBaseCollection(self._client, name)
        return self._collections[name]

    def get_collection(self, name: str) -> CloudBaseCollection:
        return self[name]


class CloudBaseClient:
    """云数据库 HTTP 客户端"""

    def __init__(self):
        self._http: Optional[httpx.AsyncClient] = None
        self._db_url: str = ""
        self.database: Optional[CloudBaseDatabase] = None
        self._configured = False

    async def connect(self) -> bool:
        """初始化连接并验证可达性"""
        if not cloudbase_config.is_configured:
            logger.warning(
                "⚠️  CloudBase 未配置 (CLOUDBASE_ENV_ID / CLOUDBASE_API_TOKEN)，"
                "将以离线模式运行——数据库操作将返回空结果"
            )
            self._configured = False
            self.database = CloudBaseDatabase(self)
            return False

        self._db_url = f"{cloudbase_config.base_url}/v1/databases"
        self._http = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {cloudbase_config.api_token}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(30.0),
        )

        try:
            url = f"{cloudbase_config.base_url}/v1/health"
            await self._http.get(url)
            self._configured = True
            logger.info("✅ CloudBase 云数据库连接成功")
        except Exception as e:
            logger.warning(f"⚠️  CloudBase 健康检查失败: {e}")
            self._configured = False

        self.database = CloudBaseDatabase(self)
        return self._configured

    async def close(self):
        """关闭 HTTP 客户端"""
        if self._http:
            await self._http.aclose()
            self._http = None
        self._configured = False

    async def _request(
        self,
        method: str,
        url: str,
        json: Optional[dict] = None,
    ) -> dict:
        """发送 HTTP 请求"""
        if not self._http or not self._configured:
            logger.warning(f"CloudBase 未连接，跳过 {method} {url}")
            return {}

        try:
            resp = await self._http.request(method, url, json=json)
            resp.raise_for_status()
            return resp.json() if resp.content else {}
        except httpx.HTTPStatusError as e:
            logger.error(f"CloudBase API 错误 {e.response.status_code}: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"CloudBase 请求失败: {e}")
            raise

    async def health_check(self) -> dict:
        """健康检查"""
        if not self._configured:
            return {"cloudbase": {"status": "not_configured"}}
        try:
            url = f"{cloudbase_config.base_url}/v1/health"
            await self._http.get(url)
            return {"cloudbase": {"status": "healthy"}}
        except Exception as e:
            return {"cloudbase": {"status": "unhealthy", "error": str(e)}}

    @property
    def is_connected(self) -> bool:
        return self._configured


# 全局客户端实例
cloudbase_client = CloudBaseClient()


# ---- 同步 CloudBase HTTP 客户端（供线程池内同步函数使用） ----

class SyncCloudBaseClient:
    """同步 CloudBase HTTP 客户端，用于线程池中的同步函数"""

    def __init__(self):
        self._http: Optional[httpx.Client] = None
        self._db_url: str = ""
        self._configured = False

    def connect(self) -> bool:
        if not cloudbase_config.is_configured:
            logger.warning("SyncCloudBase: 未配置，将返回空结果")
            self._configured = False
            return False
        self._db_url = f"{cloudbase_config.base_url}/v1/databases"
        self._http = httpx.Client(
            headers={
                "Authorization": f"Bearer {cloudbase_config.api_token}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(30.0),
        )
        self._configured = True
        return True

    def close(self):
        if self._http:
            self._http.close()
            self._http = None
        self._configured = False

    def _request(self, method: str, url: str, json: Optional[dict] = None) -> dict:
        if not self._http or not self._configured:
            return {}
        try:
            resp = self._http.request(method, url, json=json)
            resp.raise_for_status()
            return resp.json() if resp.content else {}
        except Exception as e:
            logger.error(f"SyncCloudBase 请求失败: {e}")
            return {}

    def find_one(self, collection: str, query: Optional[dict] = None, sort: Optional[list] = None) -> Optional[dict]:
        url = f"{self._db_url}/{collection}/documents"
        body: Dict[str, Any] = {"query": query or {}, "limit": 1}
        if sort:
            body["order"] = [{"field": s[0], "direction": "asc" if s[1] >= 0 else "desc"} for s in sort]
        resp = self._request("POST", url, json=body)
        docs = resp.get("documents", []) or resp.get("data", []) or []
        return docs[0] if docs else None

    def find(self, collection: str, query: Optional[dict] = None, sort_field: Optional[str] = None, sort_dir: str = "asc", limit: int = 100) -> list:
        url = f"{self._db_url}/{collection}/documents"
        body: Dict[str, Any] = {"query": query or {}, "limit": limit}
        if sort_field:
            body["order"] = [{"field": sort_field, "direction": sort_dir}]
        resp = self._request("POST", url, json=body)
        return resp.get("documents", []) or resp.get("data", []) or []

    def update_one(self, collection: str, query: dict, update: dict) -> bool:
        doc = self.find_one(collection, query)
        if not doc:
            return False
        doc_id = doc["_id"]
        set_data = update.get("$set", {})
        url = f"{self._db_url}/{collection}/documents/{doc_id}"
        self._request("PATCH", url, json={"data": set_data})
        return True

    def insert_one(self, collection: str, document: dict) -> Optional[str]:
        url = f"{self._db_url}/{collection}/documents/insert"
        resp = self._request("POST", url, json={"documents": [document]})
        ids = resp.get("inserted_ids", [])
        return ids[0] if ids else None


# 全局同步客户端实例（按需初始化）
_sync_client: Optional[SyncCloudBaseClient] = None


def get_sync_cloudbase() -> Optional[SyncCloudBaseClient]:
    """获取同步 CloudBase 客户端（按需初始化）"""
    global _sync_client
    if _sync_client is None:
        _sync_client = SyncCloudBaseClient()
        _sync_client.connect()
    return _sync_client if _sync_client._configured else None


# ---- 兼容层：替代原有 database.py 的导出 ----

async def init_db():
    """初始化云数据库连接（替代 init_database）"""
    await cloudbase_client.connect()


async def close_db():
    """关闭云数据库连接（替代 close_database）"""
    await cloudbase_client.close()


def get_mongo_db() -> CloudBaseDatabase:
    """获取数据库实例（兼容原有 get_mongo_db 调用）"""
    if cloudbase_client.database is None:
        raise RuntimeError("CloudBase 数据库未初始化，请先调用 init_db()")
    return cloudbase_client.database


def get_mongo_client() -> CloudBaseClient:
    """获取客户端（兼容原有 get_mongo_client 调用）"""
    return cloudbase_client


async def get_database_health() -> dict:
    """获取数据库健康状态"""
    return await cloudbase_client.health_check()


# ---- 进度跟踪（替代 Redis） ----

async def set_task_progress(task_id: str, openid: str, progress: float, current_step: str) -> None:
    """写入分析进度"""
    db = get_mongo_db()
    col = db["task_progress"]
    existing = await col.find_one({"task_id": task_id})
    doc = {
        "task_id": task_id,
        "openid": openid,
        "progress": progress,
        "current_step": current_step,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "expire_at": int(datetime.now(timezone.utc).timestamp()) + 86400,
    }
    if existing:
        await col.update_one({"task_id": task_id}, {"$set": doc})
    else:
        await col.insert_one(doc)


async def get_task_progress(task_id: str) -> Optional[dict]:
    """读取分析进度"""
    db = get_mongo_db()
    return await db["task_progress"].find_one({"task_id": task_id})


# ---- 限流（替代 Redis 计数器） ----

async def check_and_increment_quota(openid: str, daily_quota: int = 10) -> tuple[bool, int]:
    """检查并增加每日配额，返回 (是否允许, 已使用次数)"""
    db = get_mongo_db()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    col = db["rate_limits"]
    key = f"{openid}:{today}"

    doc = await col.find_one({"key": key})
    if doc:
        count = doc.get("count", 0)
        if count >= daily_quota:
            return False, count
        await col.update_one({"key": key}, {"$set": {"count": count + 1}})
        return True, count + 1
    else:
        await col.insert_one({"key": key, "openid": openid, "date": today, "count": 1})
        return True, 1
