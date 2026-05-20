"""
分析任务接口测试
由于 analysis 路由依赖 langchain，使用 mock 方式测试
"""
import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import FastAPI, APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.testclient import TestClient


# 创建一个简化的 analysis 路由副本用于测试
def create_analysis_test_router():
    """创建用于测试的 analysis 路由"""
    from app.routers.wechat_auth import get_current_user_wechat

    router = APIRouter()

    @router.post("/single")
    async def submit_single_analysis(
        request: dict,
        background_tasks: BackgroundTasks,
        user: dict = Depends(get_current_user_wechat),
    ):
        openid = user["openid"]
        symbol = request.get("symbol") or request.get("stock_code", "")
        if not symbol:
            raise HTTPException(status_code=400, detail="请提供股票代码 (symbol)")

        return {
            "success": True,
            "data": {"task_id": "test_task_id", "status": "pending"},
            "message": "分析任务已提交",
        }

    @router.get("/tasks/{task_id}/status")
    async def get_task_status(
        task_id: str,
        user: dict = Depends(get_current_user_wechat),
    ):
        # Import inside function to allow patching
        from app.core.cloudbase_client import get_mongo_db
        openid = user["openid"]
        db = get_mongo_db()
        task = await db["analysis_tasks"].find_one({
            "task_id": task_id,
            "$or": [
                {"openid": openid},
                {"user_id": openid},
                {"user": openid}
            ]
        })
        if task:
            return {"success": True, "data": {
                "task_id": task_id,
                "status": task.get("status", "unknown"),
                "progress": task.get("progress", 0),
                "message": task.get("message", ""),
                "symbol": task.get("symbol", ""),
            }}
        raise HTTPException(status_code=404, detail="任务不存在或无权访问")

    @router.get("/tasks/{task_id}/result")
    async def get_task_result(
        task_id: str,
        user: dict = Depends(get_current_user_wechat),
    ):
        # Import inside function to allow patching
        from app.core.cloudbase_client import get_mongo_db
        openid = user["openid"]
        db = get_mongo_db()
        result_data = await db["analysis_reports"].find_one({
            "task_id": task_id,
            "$or": [
                {"openid": openid},
                {"user_id": openid},
                {"user": openid}
            ]
        })
        if not result_data:
            raise HTTPException(status_code=404, detail="分析结果不存在或无权访问")
        return {
            "success": True,
            "data": {
                "analysis_id": result_data.get("analysis_id", ""),
                "symbol": result_data.get("stock_symbol", ""),
                "decision": result_data.get("decision", {}),
                "summary": result_data.get("summary", ""),
                "reports": result_data.get("reports", {}),
            },
            "message": "获取成功",
        }

    return router


@pytest.fixture
def analysis_app():
    """创建分析路由测试应用"""
    app = FastAPI()
    router = create_analysis_test_router()
    app.include_router(router, prefix="/api/analysis")
    return app


@pytest.fixture
def analysis_client(analysis_app) -> TestClient:
    return TestClient(analysis_app)


class TestAnalysisRoutes:
    """分析任务路由测试"""

    def test_submit_without_token(self, analysis_client):
        """测试无 token 提交分析任务"""
        response = analysis_client.post("/api/analysis/single", json={"symbol": "600519"})
        assert response.status_code == 401

    def test_submit_success(self, analysis_client, auth_headers, override_cloudbase):
        """测试成功提交分析任务"""
        response = analysis_client.post(
            "/api/analysis/single",
            json={"symbol": "600519", "stock_code": "600519"},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "task_id" in data["data"]
        assert data["data"]["status"] == "pending"

    def test_submit_returns_task_id(self, analysis_client, auth_headers, override_cloudbase):
        """测试提交分析返回 task_id"""
        response = analysis_client.post(
            "/api/analysis/single",
            json={"symbol": "600519"},
            headers=auth_headers
        )
        data = response.json()
        assert data["data"]["task_id"] is not None

    def test_task_status_own_task(self, analysis_client, auth_headers, override_cloudbase):
        """测试查询自己的任务状态"""
        db = override_cloudbase
        asyncio.get_event_loop().run_until_complete(
            db["analysis_tasks"].insert_one({
                "task_id": "task_001",
                "openid": "openid_a",
                "user_id": "openid_a",
                "symbol": "600519",
                "status": "processing",
                "progress": 50,
                "message": "分析中",
            })
        )

        response = analysis_client.get("/api/analysis/tasks/task_001/status", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["task_id"] == "task_001"

    def test_task_status_other_user_task(self, analysis_client, auth_headers, override_cloudbase):
        """测试查询他人任务状态"""
        db = override_cloudbase
        asyncio.get_event_loop().run_until_complete(
            db["analysis_tasks"].insert_one({
                "task_id": "task_b",
                "openid": "openid_b",
                "user_id": "openid_b",
                "symbol": "000001",
            })
        )

        response = analysis_client.get("/api/analysis/tasks/task_b/status", headers=auth_headers)
        assert response.status_code == 404

    def test_task_result_own_task(self, analysis_client, auth_headers, override_cloudbase):
        """测试获取自己的任务结果"""
        db = override_cloudbase
        asyncio.get_event_loop().run_until_complete(
            db["analysis_reports"].insert_one({
                "task_id": "task_001",
                "openid": "openid_a",
                "user_id": "openid_a",
                "stock_symbol": "600519",
                "decision": {"action": "买入"},
                "summary": "测试摘要",
                "reports": {"final_trade_decision": "决策内容"},
                "analysis_id": "report_001",
            })
        )

        response = analysis_client.get("/api/analysis/tasks/task_001/result", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "decision" in data["data"]
        assert "reports" in data["data"]

    def test_task_result_other_user(self, analysis_client, auth_headers, override_cloudbase):
        """测试获取他人任务结果"""
        db = override_cloudbase
        asyncio.get_event_loop().run_until_complete(
            db["analysis_reports"].insert_one({
                "task_id": "task_b",
                "openid": "openid_b",
                "user_id": "openid_b",
            })
        )

        response = analysis_client.get("/api/analysis/tasks/task_b/result", headers=auth_headers)
        assert response.status_code == 404
