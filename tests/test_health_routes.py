"""
健康检查接口测试
"""
import pytest


class TestHealthRoutes:
    """健康检查路由测试"""

    def test_health(self, health_client):
        """测试 /api/health 接口"""
        response = health_client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert data["data"]["status"] == "ok"

    def test_healthz(self, health_client):
        """测试 /api/healthz 接口"""
        response = health_client.get("/api/healthz")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"

    def test_readyz(self, health_client):
        """测试 /api/readyz 接口"""
        response = health_client.get("/api/readyz")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ready") is True

    def test_health_returns_version(self, health_client):
        """测试健康检查返回版本号"""
        response = health_client.get("/api/health")
        data = response.json()
        assert "version" in data["data"]

    def test_health_returns_timestamp(self, health_client):
        """测试健康检查返回时间戳"""
        response = health_client.get("/api/health")
        data = response.json()
        assert "timestamp" in data["data"]
