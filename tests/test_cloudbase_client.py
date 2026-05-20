"""
CloudBase 兼容层测试
测试 find_one, insert_one, update_one, upsert, $setOnInsert, $inc 等操作
"""
import pytest
import asyncio


class TestCloudBaseCollection:
    """CloudBase 集合测试"""

    @pytest.mark.asyncio
    async def test_insert_one(self, mock_db):
        """测试插入单个文档"""
        col = mock_db["test_collection"]
        result = await col.insert_one({"name": "test", "value": 1})
        
        assert result.inserted_id is not None
        doc = await col.find_one({"name": "test"})
        assert doc is not None
        assert doc["value"] == 1

    @pytest.mark.asyncio
    async def test_find_one(self, mock_db):
        """测试查询单个文档"""
        col = mock_db["test_collection"]
        await col.insert_one({"id": "t1", "name": "test1"})
        await col.insert_one({"id": "t2", "name": "test2"})
        
        doc = await col.find_one({"id": "t1"})
        assert doc is not None
        assert doc["name"] == "test1"

    @pytest.mark.asyncio
    async def test_find_one_not_found(self, mock_db):
        """测试查询不存在的文档"""
        col = mock_db["test_collection"]
        doc = await col.find_one({"id": "nonexistent"})
        assert doc is None

    @pytest.mark.asyncio
    async def test_update_one_set(self, mock_db):
        """测试 $set 更新操作"""
        col = mock_db["test_collection"]
        await col.insert_one({"task_id": "t1", "status": "pending"})
        
        await col.update_one({"task_id": "t1"}, {"$set": {"status": "completed"}})
        
        doc = await col.find_one({"task_id": "t1"})
        assert doc["status"] == "completed"

    @pytest.mark.asyncio
    async def test_update_one_inc(self, mock_db):
        """测试 $inc 自增操作"""
        col = mock_db["test_collection"]
        await col.insert_one({"key": "counter", "count": 5})
        
        await col.update_one({"key": "counter"}, {"$inc": {"count": 3}})
        
        doc = await col.find_one({"key": "counter"})
        assert doc["count"] == 8

    @pytest.mark.asyncio
    async def test_update_one_inc_missing_field(self, mock_db):
        """测试 $inc 对缺失字段自增"""
        col = mock_db["test_collection"]
        await col.insert_one({"key": "counter"})
        
        await col.update_one({"key": "counter"}, {"$inc": {"new_count": 10}})
        
        doc = await col.find_one({"key": "counter"})
        assert doc["new_count"] == 10

    @pytest.mark.asyncio
    async def test_update_one_unset(self, mock_db):
        """测试 $unset 删除字段"""
        col = mock_db["test_collection"]
        await col.insert_one({"task_id": "t1", "status": "pending", "error": "test error"})
        
        await col.update_one({"task_id": "t1"}, {"$unset": {"error": ""}})
        
        doc = await col.find_one({"task_id": "t1"})
        assert "error" not in doc

    @pytest.mark.asyncio
    async def test_update_one_upsert_insert(self, mock_db):
        """测试 upsert 插入新文档"""
        col = mock_db["test_collection"]
        
        result = await col.update_one(
            {"task_id": "new_task"},
            {"$setOnInsert": {"task_id": "new_task", "status": "pending"},
             "$set": {"created": "2026-05-20"}},
            upsert=True
        )
        
        assert result.matched_count == 0
        assert result.modified_count == 1
        assert result.upserted_id is not None
        
        doc = await col.find_one({"task_id": "new_task"})
        assert doc["status"] == "pending"
        assert doc["created"] == "2026-05-20"

    @pytest.mark.asyncio
    async def test_update_one_upsert_existing(self, mock_db):
        """测试 upsert 更新现有文档"""
        col = mock_db["test_collection"]
        await col.insert_one({"task_id": "existing", "status": "pending"})
        
        result = await col.update_one(
            {"task_id": "existing"},
            {"$setOnInsert": {"should_not_appear": True},
             "$set": {"status": "completed"}},
            upsert=True
        )
        
        assert result.matched_count == 1
        assert result.modified_count == 1
        assert result.upserted_id is None
        
        doc = await col.find_one({"task_id": "existing"})
        assert doc["status"] == "completed"
        assert "should_not_appear" not in doc

    @pytest.mark.asyncio
    async def test_update_many(self, mock_db):
        """测试批量更新"""
        col = mock_db["test_collection"]
        await col.insert_one({"user": "a", "status": "pending"})
        await col.insert_one({"user": "b", "status": "pending"})
        
        result = await col.update_many(
            {"status": "pending"},
            {"$set": {"status": "processed"}}
        )
        
        assert result.matched_count == 2
        assert result.modified_count == 2

    @pytest.mark.asyncio
    async def test_delete_one(self, mock_db):
        """测试删除文档"""
        col = mock_db["test_collection"]
        await col.insert_one({"id": "to_delete"})
        
        result = await col.delete_one({"id": "to_delete"})
        assert result.deleted_count == 1
        
        doc = await col.find_one({"id": "to_delete"})
        assert doc is None

    @pytest.mark.asyncio
    async def test_count_documents(self, mock_db):
        """测试文档计数"""
        col = mock_db["test_collection"]
        await col.insert_one({"type": "a", "value": 1})
        await col.insert_one({"type": "a", "value": 2})
        await col.insert_one({"type": "b", "value": 3})

        count = await col.count_documents({"type": "a"})
        assert count == 2

        count = await col.count_documents({})
        assert count == 3

    @pytest.mark.asyncio
    async def test_query_in_operator(self, mock_db):
        """测试 $in 操作符"""
        col = mock_db["test_collection"]
        await col.insert_one({"id": "1", "status": "pending"})
        await col.insert_one({"id": "2", "status": "completed"})
        await col.insert_one({"id": "3", "status": "failed"})

        results = []
        cursor = col.find({"status": {"$in": ["pending", "completed"]}})
        async for doc in cursor:
            results.append(doc)

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_query_comparison_operators(self, mock_db):
        """测试 $lt, $gt, $lte, $gte 比较操作符"""
        col = mock_db["test_collection"]
        for i in range(10):
            await col.insert_one({"idx": i, "value": i * 10})

        # $gt
        cursor = col.find({"value": {"$gt": 50}})
        results = await cursor.to_list()
        assert len(results) == 4  # 60, 70, 80, 90

        # $lt
        cursor = col.find({"value": {"$lt": 30}})
        results = await cursor.to_list()
        assert len(results) == 3  # 0, 10, 20

        # $gte
        cursor = col.find({"value": {"$gte": 50}})
        results = await cursor.to_list()
        assert len(results) == 5  # 50, 60, 70, 80, 90

        # $lte
        cursor = col.find({"value": {"$lte": 30}})
        results = await cursor.to_list()
        assert len(results) == 4  # 0, 10, 20, 30

    @pytest.mark.asyncio
    async def test_query_ne_operator(self, mock_db):
        """测试 $ne 操作符"""
        col = mock_db["test_collection"]
        await col.insert_one({"id": "1", "status": "pending"})
        await col.insert_one({"id": "2", "status": "completed"})

        doc = await col.find_one({"status": {"$ne": "pending"}})
        assert doc["status"] == "completed"


class TestCloudBaseCursor:
    """CloudBase Cursor 测试"""

    @pytest.mark.asyncio
    async def test_find_with_sort(self, mock_db):
        """测试排序查询"""
        col = mock_db["test_collection"]
        await col.insert_one({"id": "a", "order": 3})
        await col.insert_one({"id": "b", "order": 1})
        await col.insert_one({"id": "c", "order": 2})
        
        cursor = col.find({}).sort("order", 1)
        results = await cursor.to_list(10)
        
        assert results[0]["id"] == "b"
        assert results[1]["id"] == "c"
        assert results[2]["id"] == "a"

    @pytest.mark.asyncio
    async def test_find_with_limit(self, mock_db):
        """测试限制数量"""
        col = mock_db["test_collection"]
        for i in range(10):
            await col.insert_one({"idx": i})
        
        cursor = col.find({}).limit(5)
        results = await cursor.to_list()
        
        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_find_with_skip(self, mock_db):
        """测试跳过记录"""
        col = mock_db["test_collection"]
        for i in range(10):
            await col.insert_one({"idx": i})
        
        cursor = col.find({}).sort("idx", 1).skip(5).limit(5)
        results = await cursor.to_list()
        
        assert len(results) == 5
        assert results[0]["idx"] == 5

    @pytest.mark.asyncio
    async def test_find_async_iteration(self, mock_db):
        """测试异步迭代"""
        col = mock_db["test_collection"]
        for i in range(5):
            await col.insert_one({"idx": i})
        
        results = []
        cursor = col.find({})
        async for doc in cursor:
            results.append(doc)
        
        assert len(results) == 5
