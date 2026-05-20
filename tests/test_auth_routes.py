"""
认证接口测试
测试 POST /api/auth/login 和 GET /api/auth/me
"""
import pytest
from unittest.mock import patch


class TestAuthRoutes:
    """认证路由测试"""

    def test_me_without_token(self, auth_client):
        """测试无 token 访问 /api/auth/me"""
        response = auth_client.get("/api/auth/me")
        assert response.status_code == 401

    def test_me_with_invalid_token(self, auth_client):
        """测试无效 token 访问 /api/auth/me"""
        headers = {"Authorization": "Bearer invalid_token"}
        response = auth_client.get("/api/auth/me", headers=headers)
        assert response.status_code == 401

    def test_me_with_valid_token(self, auth_client, auth_headers, override_cloudbase):
        """测试有效 token 访问 /api/auth/me"""
        import asyncio
        db = override_cloudbase
        asyncio.get_event_loop().run_until_complete(
            db["users"].insert_one({
                "openid": "openid_a",
                "daily_quota": 10,
                "analysis_count": 0
            })
        )

        response = auth_client.get("/api/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert "data" in data
        assert "openid" in data["data"]
        assert "daily_used" in data["data"]
        assert isinstance(data["data"]["daily_used"], int)

    def test_me_with_expired_token(self, auth_client, expired_token):
        """测试过期 token 访问 /api/auth/me"""
        headers = {"Authorization": f"Bearer {expired_token}"}
        response = auth_client.get("/api/auth/me", headers=headers)
        assert response.status_code == 401

    @patch("app.routers.wechat_auth.wechat_service.code_to_session")
    def test_login_success(self, mock_code2session, auth_client, override_cloudbase):
        """测试登录成功"""
        mock_code2session.return_value = {"openid": "test_openid", "session_key": "test_key"}

        response = auth_client.post("/api/auth/login", json={"code": "test_code"})

        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert "data" in data
        assert "token" in data["data"]
        assert "openid" in data["data"]
        assert "daily_quota" in data["data"]

    @patch("app.routers.wechat_auth.wechat_service.code_to_session")
    def test_login_returns_correct_structure(self, mock_code2session, auth_client, override_cloudbase):
        """测试登录返回结构符合要求"""
        mock_code2session.return_value = {"openid": "test_openid", "session_key": "test_key"}

        response = auth_client.post("/api/auth/login", json={"code": "test_code"})
        data = response.json()

        assert data["success"] is True
        assert "token" in data["data"]
        assert "openid" in data["data"]
        assert "daily_quota" in data["data"]
        assert isinstance(data["data"]["daily_quota"], int)
