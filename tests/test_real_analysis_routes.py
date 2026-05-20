"""
真实分析路由测试
直接 import app.routers.analysis.router 并用 monkeypatch 隔离依赖
"""
import pytest
import sys
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient


# Pre-mock problematic imports before any app imports
def _setup_mocks():
    """Setup all required mocks before importing analysis router"""
    if 'langchain_openai' not in sys.modules:
        mock_langchain = MagicMock()
        mock_langchain.ChatOpenAI = MagicMock()
        sys.modules['langchain_openai'] = mock_langchain

    if 'chromadb' not in sys.modules:
        mock_chroma = MagicMock()
        sys.modules['chromadb'] = mock_chroma

    if 'tradingagents.agents.utils.memory' not in sys.modules:
        mock_memory = MagicMock()
        mock_memory.FinancialSituationMemory = MagicMock()
        sys.modules['tradingagents.agents.utils.memory'] = mock_memory

    if 'tradingagents.graph.trading_graph' not in sys.modules:
        mock_graph = MagicMock()
        mock_graph.TradingAgentsGraph = MagicMock()
        sys.modules['tradingagents.graph.trading_graph'] = mock_graph


_setup_mocks()


class FakeAnalysisService:
    """模拟分析服务"""

    def __init__(self):
        self.tasks = {}

    async def create_analysis_task(self, openid, request):
        symbol = request.get_symbol()
        task_id = f"task_{symbol}"
        self.tasks[task_id] = {"task_id": task_id, "status": "pending"}
        return {"task_id": task_id, "status": "pending"}

    async def execute_analysis_background(self, task_id, openid, request):
        return None

    async def get_task_status(self, task_id):
        return self.tasks.get(task_id)


async def fake_check_and_increment_quota(openid, quota):
    return True, 1


async def quota_exhausted(openid, quota):
    return False, 10


@pytest.fixture
def analysis_real_app():
    """创建使用真实 analysis router 的测试应用"""
    _setup_mocks()

    from app.routers.analysis import router
    app = FastAPI()
    app.include_router(router, prefix="/api/analysis")
    return app


@pytest.fixture
def analysis_real_client(analysis_real_app):
    return TestClient(analysis_real_app)


@pytest.fixture
def fake_service():
    return FakeAnalysisService()


class TestRealAnalysisRoutes:
    """真实分析路由测试"""

    def test_submit_single_analysis_success(self, analysis_real_client, auth_headers, override_cloudbase, fake_service):
        """测试提交单股分析成功"""
        import asyncio
        db = override_cloudbase

        asyncio.get_event_loop().run_until_complete(
            db["users"].insert_one({
                "openid": "openid_a",
                "daily_quota": 10,
                "analysis_count": 0
            })
        )

        with patch("app.routers.analysis.get_simple_analysis_service", return_value=fake_service), \
             patch("app.routers.analysis.check_and_increment_quota", fake_check_and_increment_quota), \
             patch("app.services.simple_analysis_service.get_mongo_db", return_value=db):

            response = analysis_real_client.post(
                "/api/analysis/single",
                headers=auth_headers,
                json={
                    "symbol": "600519",
                    "stock_code": "600519",
                    "parameters": {
                        "market_type": "A股",
                        "research_depth": "标准",
                        "selected_analysts": ["market", "fundamentals"]
                    }
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "task_id" in data["data"]
            assert data["data"]["status"] == "pending"

    def test_submit_without_symbol_fails(self, analysis_real_client, auth_headers, override_cloudbase, fake_service):
        """测试缺少股票代码失败"""
        import asyncio
        db = override_cloudbase
        asyncio.get_event_loop().run_until_complete(
            db["users"].insert_one({
                "openid": "openid_a",
                "daily_quota": 10,
                "analysis_count": 0
            })
        )

        with patch("app.routers.analysis.get_simple_analysis_service", return_value=fake_service), \
             patch("app.routers.analysis.check_and_increment_quota", fake_check_and_increment_quota), \
             patch("app.services.simple_analysis_service.get_mongo_db", return_value=db):

            response = analysis_real_client.post(
                "/api/analysis/single",
                headers=auth_headers,
                json={
                    "parameters": {
                        "market_type": "A股"
                    }
                }
            )

            assert response.status_code == 400

    def test_submit_quotas_exhausted(self, analysis_real_client, auth_headers, override_cloudbase, fake_service):
        """测试配额耗尽"""
        import asyncio
        db = override_cloudbase
        asyncio.get_event_loop().run_until_complete(
            db["users"].insert_one({
                "openid": "openid_a",
                "daily_quota": 10,
                "analysis_count": 10
            })
        )

        with patch("app.routers.analysis.get_simple_analysis_service", return_value=fake_service), \
             patch("app.routers.analysis.check_and_increment_quota", quota_exhausted), \
             patch("app.services.simple_analysis_service.get_mongo_db", return_value=db):

            response = analysis_real_client.post(
                "/api/analysis/single",
                headers=auth_headers,
                json={
                    "symbol": "600519"
                }
            )

            assert response.status_code == 429

    def test_task_status_own_task(self, analysis_real_client, auth_headers, override_cloudbase, fake_service):
        """测试查询自己的任务状态"""
        import asyncio
        from datetime import datetime
        db = override_cloudbase
        # Use naive datetime to match analysis.py's datetime.utcnow()
        started_at = datetime.utcnow()

        asyncio.get_event_loop().run_until_complete(
            db["analysis_tasks"].insert_one({
                "task_id": "task_001",
                "openid": "openid_a",
                "user_id": "openid_a",
                "symbol": "600519",
                "status": "completed",
                "progress": 100,
                "message": "test complete",
                "started_at": started_at,
                "created_at": started_at
            })
        )

        fake_service.tasks = {}

        with patch("app.routers.analysis.get_simple_analysis_service", return_value=fake_service), \
             patch("app.routers.analysis.get_mongo_db", return_value=db), \
             patch("app.services.simple_analysis_service.get_mongo_db", return_value=db):
            response = analysis_real_client.get(
                "/api/analysis/tasks/task_001/status",
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["task_id"] == "task_001"
            assert data["data"]["status"] == "completed"

    def test_task_status_other_user_task(self, analysis_real_client, auth_headers, override_cloudbase, fake_service):
        """测试查询他人任务状态返回404"""
        import asyncio
        from datetime import datetime
        db = override_cloudbase
        started_at = datetime.utcnow()

        asyncio.get_event_loop().run_until_complete(
            db["analysis_tasks"].insert_one({
                "task_id": "task_b",
                "openid": "openid_b",
                "user_id": "openid_b",
                "symbol": "000001",
                "started_at": started_at,
                "created_at": started_at
            })
        )

        fake_service.tasks = {}

        with patch("app.routers.analysis.get_simple_analysis_service", return_value=fake_service), \
             patch("app.routers.analysis.get_mongo_db", return_value=db), \
             patch("app.services.simple_analysis_service.get_mongo_db", return_value=db):
            response = analysis_real_client.get(
                "/api/analysis/tasks/task_b/status",
                headers=auth_headers
            )

            assert response.status_code == 404
