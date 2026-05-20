"""
权限隔离测试
测试用户 A 不能读取用户 B 的任务和报告
"""
import pytest
import asyncio
from unittest.mock import patch, AsyncMock


class TestReportPermissions:
    """报告权限隔离测试"""

    def test_user_a_can_read_own_report_detail(self, reports_client, auth_headers, override_cloudbase):
        """用户 A 能读取自己的报告详情"""
        db = override_cloudbase
        asyncio.get_event_loop().run_until_complete(
            db["analysis_reports"].insert_one({
                "analysis_id": "report_a",
                "task_id": "task_a",
                "openid": "openid_a",
                "user_id": "openid_a",
                "stock_symbol": "600519",
                "summary": "用户A的报告",
                "reports": {"final_trade_decision": "决策内容"},
            })
        )

        response = reports_client.get("/api/reports/report_a/detail", headers=auth_headers)
        assert response.status_code == 200

    def test_user_b_cannot_read_user_a_report_detail(self, reports_client, auth_headers_b, override_cloudbase):
        """用户 B 不能读取用户 A 的报告详情"""
        db = override_cloudbase
        asyncio.get_event_loop().run_until_complete(
            db["analysis_reports"].insert_one({
                "analysis_id": "report_a",
                "openid": "openid_a",
                "user_id": "openid_a",
                "stock_symbol": "600519",
            })
        )

        response = reports_client.get("/api/reports/report_a/detail", headers=auth_headers_b)
        assert response.status_code == 404

    def test_user_b_cannot_read_user_a_report_module(self, reports_client, auth_headers_b, override_cloudbase):
        """用户 B 不能读取用户 A 的报告模块"""
        db = override_cloudbase
        asyncio.get_event_loop().run_until_complete(
            db["analysis_reports"].insert_one({
                "analysis_id": "report_a",
                "openid": "openid_a",
                "user_id": "openid_a",
                "reports": {"final_trade_decision": "决策内容"},
            })
        )

        response = reports_client.get("/api/reports/report_a/content/final_trade_decision", headers=auth_headers_b)
        assert response.status_code == 404

    def test_report_list_only_shows_own_reports(self, reports_client, auth_headers, auth_headers_b, override_cloudbase):
        """报告列表只显示自己的报告"""
        db = override_cloudbase

        # 用户 A 的报告
        asyncio.get_event_loop().run_until_complete(
            db["analysis_reports"].insert_one({"analysis_id": "report_a1", "openid": "openid_a", "stock_symbol": "600519"})
        )
        asyncio.get_event_loop().run_until_complete(
            db["analysis_reports"].insert_one({"analysis_id": "report_a2", "openid": "openid_a", "stock_symbol": "000001"})
        )
        # 用户 B 的报告
        asyncio.get_event_loop().run_until_complete(
            db["analysis_reports"].insert_one({"analysis_id": "report_b1", "openid": "openid_b", "stock_symbol": "300750"})
        )

        # 用户 A 查询
        resp_a = reports_client.get("/api/reports/list", headers=auth_headers)
        data_a = resp_a.json()
        assert data_a["data"]["total"] == 2

        # 用户 B 查询
        resp_b = reports_client.get("/api/reports/list", headers=auth_headers_b)
        data_b = resp_b.json()
        assert data_b["data"]["total"] == 1
        assert data_b["data"]["reports"][0]["analysis_id"] == "report_b1"
