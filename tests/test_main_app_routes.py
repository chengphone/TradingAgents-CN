"""
主应用路由注册测试
验证 app.main.app 核心路由正确注册
"""
import pytest
import sys
from unittest.mock import MagicMock

# Pre-mock problematic imports
if 'langchain_openai' not in sys.modules:
    sys.modules['langchain_openai'] = MagicMock()
if 'chromadb' not in sys.modules:
    sys.modules['chromadb'] = MagicMock()
if 'tradingagents.agents.utils.memory' not in sys.modules:
    sys.modules['tradingagents.agents.utils.memory'] = MagicMock()
if 'tradingagents.graph.trading_graph' not in sys.modules:
    sys.modules['tradingagents.graph.trading_graph'] = MagicMock()


def _get_app_routes():
    """获取主应用的路由列表"""
    from app.main import app
    return {route.path for route in app.routes}


class TestMainAppRoutes:
    """主应用路由注册测试"""

    def test_health_routes_registered(self):
        """测试健康检查路由已注册"""
        paths = _get_app_routes()
        assert "/api/health" in paths
        assert "/api/healthz" in paths
        assert "/api/readyz" in paths

    def test_auth_routes_registered(self):
        """测试认证路由已注册"""
        paths = _get_app_routes()
        assert "/api/auth/login" in paths
        assert "/api/auth/me" in paths

    def test_analysis_routes_registered(self):
        """测试分析任务路由已注册"""
        paths = _get_app_routes()
        assert "/api/analysis/single" in paths
        assert "/api/analysis/tasks/{task_id}/status" in paths
        assert "/api/analysis/tasks/{task_id}/result" in paths
        assert "/api/analysis/tasks" in paths
        assert "/api/analysis/history" in paths

    def test_reports_routes_registered(self):
        """测试报告路由已注册"""
        paths = _get_app_routes()
        assert "/api/reports/list" in paths
        assert "/api/reports/{report_id}/detail" in paths
        assert "/api/reports/{report_id}/content/{module}" in paths

    def test_all_core_routes_have_api_prefix(self):
        """测试所有核心路由都有 /api 前缀"""
        from app.main import app

        # Get all route paths, excluding docs, mounts, and root
        all_paths = [getattr(route, 'path', '') for route in app.routes]
        business_paths = [p for p in all_paths
                          if p and p != '/'
                          and not p.startswith('/{')
                          and not p.startswith('/docs')
                          and not p.startswith('/openapi')
                          and not p.startswith('/redoc')]

        # All business routes should start with /api
        for path in business_paths:
            assert path.startswith('/api'), f"路由 {path} 缺少 /api 前缀"