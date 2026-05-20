"""系统配置摘要（只读）"""

from fastapi import APIRouter, Depends
from typing import Any, Dict
import re

from app.core.config import settings
from app.routers.wechat_auth import get_current_user_wechat

router = APIRouter()

SENSITIVE_KEYS = {"MONGODB_PASSWORD", "REDIS_PASSWORD", "JWT_SECRET", "CSRF_SECRET", "STOCK_DATA_API_KEY"}
MASK = "***"


def _mask_value(key: str, value: Any) -> Any:
    if value is None:
        return None
    if key in SENSITIVE_KEYS:
        return MASK
    if key in {"MONGO_URI", "REDIS_URL"} and isinstance(value, str):
        v = value
        v = re.sub(r"(mongodb://[^:/?#]+):([^@/]+)@", r"\1:***@", v)
        v = re.sub(r"(redis://:)[^@/]+@", r"\1***@", v)
        return v
    return value


@router.get("/config/summary", tags=["system"])
async def get_config_summary(
    current_user: dict = Depends(get_current_user_wechat),
) -> Dict[str, Any]:
    raw = settings.model_dump()
    raw["MONGO_URI"] = "<cloudbase>"
    raw["REDIS_URL"] = "<removed>"
    return {"settings": {k: _mask_value(k, v) for k, v in raw.items()}}
