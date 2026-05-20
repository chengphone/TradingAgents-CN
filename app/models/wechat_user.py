"""微信用户模型（简化版，仅基于 openid）"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class WeChatUser(BaseModel):
    openid: str
    unionid: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: datetime = Field(default_factory=datetime.utcnow)
    analysis_count: int = 0
    daily_quota: int = 10
    is_blocked: bool = False


class WeChatLoginRequest(BaseModel):
    code: str = Field(..., description="wx.login 返回的临时 code")


class WeChatLoginResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None


class WeChatUserInfo(BaseModel):
    openid: str
    created_at: str
    analysis_count: int
    daily_quota: int
    daily_used: int = 0
