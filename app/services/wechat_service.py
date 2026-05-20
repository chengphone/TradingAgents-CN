"""微信服务：code2session、用户管理、JWT 签发"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
import jwt

from app.core.config import settings
from app.core.cloudbase_client import get_mongo_db

logger = logging.getLogger(__name__)


class WechatService:
    WECHAT_API = "https://api.weixin.qq.com/sns/jscode2session"

    async def code_to_session(self, code: str) -> dict:
        """用 wx.login 的 code 换取 openid 和 session_key"""
        params = {
            "appid": settings.WECHAT_APPID,
            "secret": settings.WECHAT_SECRET,
            "js_code": code,
            "grant_type": "authorization_code",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(self.WECHAT_API, params=params)
            data = resp.json()

        if "errcode" in data and data["errcode"] != 0:
            logger.error(f"微信 code2session 失败: {data}")
            raise ValueError(f"微信登录失败: {data.get('errmsg', '未知错误')}")

        return {
            "openid": data.get("openid"),
            "session_key": data.get("session_key"),
            "unionid": data.get("unionid"),
        }

    async def find_or_create_user(self, openid: str) -> dict:
        """通过 openid 查找或创建用户"""
        db = get_mongo_db()
        col = db["users"]
        user = await col.find_one({"openid": openid})

        if user:
            await col.update_one(
                {"openid": openid},
                {"$set": {"last_login": datetime.now(timezone.utc).isoformat()}},
            )
            return user

        doc = {
            "openid": openid,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_login": datetime.now(timezone.utc).isoformat(),
            "analysis_count": 0,
            "daily_quota": settings.WECHAT_DAILY_QUOTA,
            "is_blocked": False,
        }
        await col.insert_one(doc)
        logger.info(f"新微信用户注册: openid={openid[:10]}...")
        return doc

    def create_token(self, openid: str) -> str:
        """签发 JWT token"""
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
        payload = {
            "sub": openid,
            "type": "wechat_miniprogram",
            "exp": expire,
            "iat": datetime.now(timezone.utc),
        }
        return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")

    def verify_token(self, token: str) -> str:
        """验证 JWT token，返回 openid"""
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        if payload.get("type") != "wechat_miniprogram":
            raise ValueError("无效的 token 类型")
        return payload["sub"]

    async def get_daily_usage(self, openid: str) -> int:
        """查询今日已使用配额"""
        db = get_mongo_db()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        doc = await db["rate_limits"].find_one({"openid": openid, "date": today})
        return doc.get("count", 0) if doc else 0


wechat_service = WechatService()
