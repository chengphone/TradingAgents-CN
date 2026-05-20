"""
LLM 配置管理路由（微信小程序版）
仅保留大模型配置的增删改查
"""

from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException, Query

from app.routers.wechat_auth import get_current_user_wechat
from app.core.cloudbase_client import get_mongo_db
import logging

logger = logging.getLogger("webapi")
router = APIRouter()


# ---- LLM 配置 ----

@router.get("/config/llm")
async def get_llm_configs(
    user: dict = Depends(get_current_user_wechat),
):
    """获取所有启用的 LLM 配置"""
    try:
        db = get_mongo_db()
        doc = await db["system_configs"].find_one({"config_key": "llm_configs"})
        configs = doc.get("data", []) if doc else []

        # 只返回启用的
        active = [c for c in configs if c.get("enabled", True)]
        return {"success": True, "data": active, "message": "获取成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config/llm")
async def save_llm_config(
    payload: Dict[str, Any],
    user: dict = Depends(get_current_user_wechat),
):
    """添加或更新 LLM 配置"""
    try:
        db = get_mongo_db()
        doc = await db["system_configs"].find_one({"config_key": "llm_configs"})
        configs: List[dict] = doc.get("data", []) if doc else []

        provider = payload.get("provider", "")
        model_name = payload.get("model_name", "")

        # 更新已有或新增
        found = False
        for c in configs:
            if c.get("provider") == provider and c.get("model_name") == model_name:
                c.update(payload)
                found = True
                break
        if not found:
            configs.append(payload)

        if doc:
            await db["system_configs"].update_one(
                {"config_key": "llm_configs"},
                {"$set": {"data": configs, "updated_at": None}},
            )
        else:
            await db["system_configs"].insert_one({
                "config_key": "llm_configs",
                "data": configs,
            })

        # 同步到 tradingagents 引擎
        try:
            from app.core.config_bridge import sync_pricing_config_now
            sync_pricing_config_now()
        except Exception:
            pass

        return {"success": True, "data": {"message": "配置已保存"}, "message": "保存成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config/llm/providers")
async def get_llm_providers(
    user: dict = Depends(get_current_user_wechat),
):
    """获取可用 LLM 提供商列表（从 llm_configs 中提取）"""
    try:
        db = get_mongo_db()
        doc = await db["system_configs"].find_one({"config_key": "llm_configs"})
        configs = doc.get("data", []) if doc else []

        # 从配置中提取不重复的提供商名称
        providers = sorted(set(
            c.get("provider", "") for c in configs if c.get("provider")
        ))
        return {"success": True, "data": providers, "message": "获取成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
