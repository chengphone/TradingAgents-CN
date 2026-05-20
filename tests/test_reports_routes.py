"""
报告接口测试
测试 GET /api/reports/list, GET /api/reports/{report_id}/detail,
GET /api/reports/{report_id}/content/{module}
"""
import pytest
import asyncio


class TestReportsRoutes:
    """报告路由测试"""

    def test_list_without_token(self, reports_client):
        """测试无 token 获取报告列表"""
        response = reports_client.get("/api/reports/list")
        assert response.status_code == 401

    def test_list_with_valid_token(self, reports_client, auth_headers, override_cloudbase):
        """测试获取报告列表"""
        db = override_cloudbase
        asyncio.get_event_loop().run_until_complete(
            db["analysis_reports"].insert_one({
                "analysis_id": "report_001",
                "openid": "openid_a",
                "user_id": "openid_a",
                "stock_symbol": "600519",
                "stock_name": "贵州茅台",
                "summary": "测试摘要",
                "created_at": "2026-05-20T10:00:00Z",
            })
        )

        response = reports_client.get("/api/reports/list", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert "reports" in data["data"]
        assert "total" in data["data"]

    def test_list_only_own_reports(self, reports_client, auth_headers, override_cloudbase):
        """测试只返回自己的报告"""
        db = override_cloudbase
        asyncio.get_event_loop().run_until_complete(
            db["analysis_reports"].insert_one({"analysis_id": "report_a", "openid": "openid_a", "stock_symbol": "600519"})
        )
        asyncio.get_event_loop().run_until_complete(
            db["analysis_reports"].insert_one({"analysis_id": "report_b", "openid": "openid_b", "stock_symbol": "000001"})
        )

        response = reports_client.get("/api/reports/list", headers=auth_headers)
        data = response.json()
        reports = data["data"]["reports"]
        assert len(reports) == 1
        assert reports[0]["analysis_id"] == "report_a"

    def test_detail_own_report(self, reports_client, auth_headers, override_cloudbase):
        """测试获取自己报告的详情"""
        db = override_cloudbase
        asyncio.get_event_loop().run_until_complete(
            db["analysis_reports"].insert_one({
                "analysis_id": "report_001",
                "task_id": "task_001",
                "openid": "openid_a",
                "user_id": "openid_a",
                "stock_symbol": "600519",
                "stock_name": "贵州茅台",
                "decision": {"action": "买入"},
                "summary": "测试摘要",
                "recommendation": "建议买入",
                "reports": {"final_trade_decision": "决策内容"},
            })
        )

        response = reports_client.get("/api/reports/report_001/detail", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["stock_symbol"] == "600519"
        assert "decision" in data["data"]
        assert "reports" in data["data"]

    def test_detail_other_user_report(self, reports_client, auth_headers, override_cloudbase):
        """测试获取他人报告详情"""
        db = override_cloudbase
        asyncio.get_event_loop().run_until_complete(
            db["analysis_reports"].insert_one({
                "analysis_id": "report_b",
                "openid": "openid_b",
                "user_id": "openid_b",
            })
        )

        response = reports_client.get("/api/reports/report_b/detail", headers=auth_headers)
        assert response.status_code == 404

    def test_content_own_report(self, reports_client, auth_headers, override_cloudbase):
        """测试获取自己报告的模块内容"""
        db = override_cloudbase
        asyncio.get_event_loop().run_until_complete(
            db["analysis_reports"].insert_one({
                "analysis_id": "report_001",
                "openid": "openid_a",
                "user_id": "openid_a",
                "reports": {"market_report": "市场分析内容"},
            })
        )

        response = reports_client.get("/api/reports/report_001/content/market_report", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["module"] == "market_report"
        assert "content" in data["data"]

    def test_content_other_user_report(self, reports_client, auth_headers, override_cloudbase):
        """测试获取他人报告模块内容"""
        db = override_cloudbase
        asyncio.get_event_loop().run_until_complete(
            db["analysis_reports"].insert_one({
                "analysis_id": "report_b",
                "openid": "openid_b",
                "user_id": "openid_b",
                "reports": {"final_trade_decision": "内容"},
            })
        )

        response = reports_client.get("/api/reports/report_b/content/final_trade_decision", headers=auth_headers)
        assert response.status_code == 404

    def test_content_nonexistent_module(self, reports_client, auth_headers, override_cloudbase):
        """测试获取不存在的模块"""
        db = override_cloudbase
        asyncio.get_event_loop().run_until_complete(
            db["analysis_reports"].insert_one({
                "analysis_id": "report_001",
                "openid": "openid_a",
                "reports": {"final_trade_decision": "内容"},
            })
        )

        response = reports_client.get("/api/reports/report_001/content/nonexistent_module", headers=auth_headers)
        assert response.status_code == 404

    def test_list_pagination_second_page(self, reports_client, auth_headers, override_cloudbase):
        """测试报告列表分页第二页"""
        db = override_cloudbase

        # Insert 25 reports for user A
        for i in range(25):
            asyncio.get_event_loop().run_until_complete(
                db["analysis_reports"].insert_one({
                    "analysis_id": f"report_{i:03d}",
                    "openid": "openid_a",
                    "stock_symbol": "600519",
                    "created_at": f"2026-05-20T10:{i:02d}:00Z",
                })
            )

        # Get first page
        response = reports_client.get("/api/reports/list?page=1&page_size=10", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["total"] == 25
        assert len(data["data"]["reports"]) == 10

        # Get second page
        response = reports_client.get("/api/reports/list?page=2&page_size=10", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["total"] == 25
        assert len(data["data"]["reports"]) == 10

        # Get last page
        response = reports_client.get("/api/reports/list?page=3&page_size=10", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["total"] == 25
        assert len(data["data"]["reports"]) == 5
