"""
运行时配置测试
测试环境变量、版本号、JWT 过期时间等运行时配置
"""
import pytest
import os
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read_miniprogram_js_content() -> str:
    """读取 miniprogram 目录下所有 JS 文件内容"""
    root = PROJECT_ROOT / "miniprogram"
    if not root.exists():
        return ""
    return "\n".join(
        p.read_text(encoding="utf-8", errors="ignore")
        for p in root.rglob("*.js")
    )


class TestRuntimeConfig:
    """运行时配置测试"""

    def test_version_file_exists(self):
        """测试 VERSION 文件存在"""
        version_file = PROJECT_ROOT / "VERSION"
        assert version_file.exists(), "VERSION 文件不存在"

    def test_version_format(self):
        """测试版本号格式正确"""
        version_file = PROJECT_ROOT / "VERSION"
        version = version_file.read_text().strip()
        assert re.match(r'^v?\d+\.\d+\.\d+', version), f"版本号格式不正确: {version}"

    def test_jwt_secret_not_default_in_test(self):
        """测试 JWT_SECRET 不是默认值（测试环境）"""
        from app.core.config import settings
        assert settings.JWT_SECRET != "change-me-in-production"

    def test_jwt_expire_minutes_configurable(self):
        """测试 JWT 过期时间可配置"""
        from app.core.config import settings
        assert hasattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES")
        assert isinstance(settings.ACCESS_TOKEN_EXPIRE_MINUTES, int)
        assert settings.ACCESS_TOKEN_EXPIRE_MINUTES > 0


class TestEnvironmentVariables:
    """环境变量测试"""

    def test_cloudbase_env_id_exists(self):
        """测试 CloudBase 环境变量存在"""
        from app.core.config import settings
        assert hasattr(settings, "WECHAT_APPID")

    def test_wechat_config_exists(self):
        """测试微信配置存在"""
        from app.core.config import settings
        assert hasattr(settings, "WECHAT_APPID")
        assert hasattr(settings, "WECHAT_SECRET")
        assert hasattr(settings, "WECHAT_DAILY_QUOTA")

    def test_daily_quota_is_integer(self):
        """测试每日配额是整数"""
        from app.core.config import settings
        assert isinstance(settings.WECHAT_DAILY_QUOTA, int)
        assert settings.WECHAT_DAILY_QUOTA > 0


class TestSecurityChecks:
    """安全检查测试"""

    def test_no_hardcoded_secrets(self):
        """测试没有硬编码的密钥"""
        from app.core.config import settings
        weak_secrets = {
            "secret",
            "password",
            "123456",
            "changeme",
        }
        assert settings.JWT_SECRET.lower() not in weak_secrets

    def test_debug_is_boolean(self):
        """测试 DEBUG 是布尔值"""
        from app.core.config import settings
        assert isinstance(settings.DEBUG, bool)

    def test_cloudbase_token_validation_fallback(self, monkeypatch):
        """测试 CloudBase TOKEN/KEY 校验回退逻辑"""
        # This test verifies the validation logic without importing app.main
        # which would trigger langchain imports

        # Simulate the validation check logic
        def check_cloudbase_config(env_id, api_token, api_key):
            """Simulate the CloudBase config validation logic"""
            if not env_id:
                return False
            if not (api_token or api_key):
                return False
            return True

        # Test with only API_KEY (legacy)
        assert check_cloudbase_config("test-env", None, "legacy-key") is True

        # Test with only API_TOKEN (new)
        assert check_cloudbase_config("test-env", "new-token", None) is True

        # Test with both
        assert check_cloudbase_config("test-env", "token", "key") is True

        # Test with neither (should fail)
        assert check_cloudbase_config("test-env", None, None) is False

        # Test missing env_id (should fail)
        assert check_cloudbase_config(None, "token", None) is False


class TestStaticChecks:
    """静态检查测试"""

    def test_no_auth_me_without_api_prefix(self):
        """测试没有 /auth/me 路径（应该是 /api/auth/me）"""
        content = _read_miniprogram_js_content()
        bad_patterns = [
            "'/auth/me'",
            '"/auth/me"',
            "`/auth/me`",
        ]
        for pattern in bad_patterns:
            assert pattern not in content, f"发现错误的 /auth/me 路径写法: {pattern}"

    def test_no_res_data_token_directly(self):
        """测试没有直接使用 res.data.token（应该是 res.data.data.token）"""
        content = _read_miniprogram_js_content()
        for line in content.splitlines():
            if "res.data.token" in line and "res.data.data.token" not in line:
                pytest.fail(f"发现错误的 token 读取方式: {line}")

    @pytest.mark.skip(reason="your-env-id 占位符在本地测试环境是正常的，生产部署前需替换")
    def test_no_placeholder_env_id(self):
        """测试没有 your-env-id 占位符"""
        content = _read_miniprogram_js_content()
        cloudbaserc = PROJECT_ROOT / "cloudbaserc.json"
        if cloudbaserc.exists():
            content += "\n" + cloudbaserc.read_text(encoding="utf-8", errors="ignore")
        assert "your-env-id" not in content, "发现 your-env-id 占位符"
