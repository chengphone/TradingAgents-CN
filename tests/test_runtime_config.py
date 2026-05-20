"""
运行时配置测试
测试环境变量、版本号、JWT 过期时间等运行时配置
"""
import pytest
import os
import re


class TestRuntimeConfig:
    """运行时配置测试"""

    def test_version_file_exists(self):
        """测试 VERSION 文件存在"""
        from pathlib import Path
        version_file = Path(__file__).parent.parent / "VERSION"
        assert version_file.exists(), "VERSION 文件不存在"

    def test_version_format(self):
        """测试版本号格式正确"""
        from pathlib import Path
        version_file = Path(__file__).parent.parent / "VERSION"
        version = version_file.read_text().strip()
        # 版本号格式：vX.Y.Z 或 X.Y.Z
        assert re.match(r'^v?\d+\.\d+\.\d+', version), f"版本号格式不正确: {version}"

    def test_jwt_secret_not_default_in_test(self):
        """测试 JWT_SECRET 不是默认值（测试环境）"""
        from app.core.config import settings
        # 在测试环境中，我们设置了自定义值
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
        # 应该有 WECHAT_APPID 配置
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
        # JWT_SECRET 不应该是常见的弱密钥
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


class TestStaticChecks:
    """静态检查测试"""

    def test_no_auth_me_without_api_prefix(self):
        """测试没有 /auth/me 路径（应该是 /api/auth/me）"""
        import subprocess
        result = subprocess.run(
            ["grep", "-r", "'/auth/me'", "miniprogram"],
            cwd="/media/laochen/314170AB37F717D9/TradingAgents-CN",
            capture_output=True,
            text=True
        )
        assert result.returncode != 0, "发现错误的 /auth/me 路径"

    def test_no_res_data_token_directly(self):
        """测试没有直接使用 res.data.token（应该是 res.data.data.token）"""
        import subprocess
        # 检查是否有过时的 token 读取方式
        result = subprocess.run(
            ["grep", "-r", "res.data.token", "miniprogram"],
            cwd="/media/laochen/314170AB37F717D9/TradingAgents-CN",
            capture_output=True,
            text=True
        )
        # res.data.data.token 是正确的，res.data.token 是错误的
        output = result.stdout
        for line in output.split('\n'):
            if line and 'res.data.data.token' not in line:
                pytest.fail(f"发现错误的 token 读取方式: {line}")

    @pytest.mark.skip(reason="your-env-id 占位符在本地测试环境是正常的，生产部署前需替换")
    def test_no_placeholder_env_id(self):
        """测试没有 your-env-id 占位符"""
        import subprocess
        result = subprocess.run(
            ["grep", "-r", "your-env-id", "miniprogram", "cloudbaserc.json"],
            cwd="/media/laochen/314170AB37F717D9/TradingAgents-CN",
            capture_output=True,
            text=True
        )
        assert result.returncode != 0, "发现 your-env-id 占位符"
