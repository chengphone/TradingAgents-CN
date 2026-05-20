"""微信登录路由"""

from fastapi import APIRouter, HTTPException, Header, Depends
from typing import Optional

from app.models.wechat_user import WeChatLoginRequest
from app.services.wechat_service import wechat_service

router = APIRouter()


async def get_current_user_wechat(
    authorization: Optional[str] = Header(default=None),
) -> dict:
    """依赖注入：从 Bearer token 解析当前微信用户"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录，请先微信授权")

    token = authorization[len("Bearer "):]
    try:
        openid = wechat_service.verify_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="登录已过期，请重新授权")

    return {"openid": openid, "id": openid}


@router.post("/login")
async def wechat_login(req: WeChatLoginRequest):
    """微信静默登录：code 换 token"""
    try:
        session = await wechat_service.code_to_session(req.code)
        openid = session["openid"]
        user = await wechat_service.find_or_create_user(openid)
        token = wechat_service.create_token(openid)

        return {
            "success": True,
            "data": {
                "token": token,
                "openid": openid,
                "daily_quota": user.get("daily_quota", 10),
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"登录服务异常: {e}")


@router.get("/me")
async def wechat_me(current_user: dict = Depends(get_current_user_wechat)):
    """获取当前用户信息"""
    openid = current_user["openid"]
    db_user = await wechat_service.find_or_create_user(openid)
    daily_used = await wechat_service.get_daily_usage(openid)

    return {
        "success": True,
        "data": {
            "openid": openid,
            "created_at": str(db_user.get("created_at", "")),
            "analysis_count": db_user.get("analysis_count", 0),
            "daily_quota": db_user.get("daily_quota", 10),
            "daily_used": daily_used,
        },
    }
