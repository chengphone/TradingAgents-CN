"""
分析报告管理API路由（微信小程序版）
"""

from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.routers.wechat_auth import get_current_user_wechat
from app.core.cloudbase_client import get_mongo_db
import logging

logger = logging.getLogger("webapi")

router = APIRouter(tags=["reports"])


def _fmt_time(t) -> str:
    """安全格式化时间为 ISO 字符串"""
    if t is None:
        return ""
    if isinstance(t, datetime):
        return t.isoformat()
    return str(t)


@router.get("/reports/list")
async def get_reports_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    stock_code: Optional[str] = Query(None),
    user: dict = Depends(get_current_user_wechat),
):
    """获取分析报告列表（按 openid 过滤）"""
    try:
        openid = user["openid"]
        db = get_mongo_db()

        query = {"openid": openid}
        if stock_code:
            query["stock_symbol"] = stock_code

        total = await db["analysis_reports"].count_documents(query)
        skip = (page - 1) * page_size

        cursor = (
            db["analysis_reports"]
            .find(query)
            .sort("created_at", -1)
            .limit(page_size)
        )
        # 手动 skip（CloudBase API 不直接支持 offset）
        # 使用简单的 skip 逻辑
        skipped = 0
        reports = []
        async for doc in cursor:
            if skipped < skip:
                skipped += 1
                continue
            reports.append({
                "analysis_id": doc.get("analysis_id", ""),
                "symbol": doc.get("stock_symbol", ""),
                "stock_name": doc.get("stock_name", ""),
                "decision": doc.get("decision", {}),
                "summary": (doc.get("summary", "") or "")[:200],
                "created_at": _fmt_time(doc.get("created_at")),
                "status": doc.get("status", "completed"),
            })

        return {
            "success": True,
            "data": {"reports": reports, "total": total, "page": page, "page_size": page_size},
            "message": "获取成功",
        }
    except Exception as e:
        logger.error(f"获取报告列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/{report_id}/detail")
async def get_report_detail(
    report_id: str,
    user: dict = Depends(get_current_user_wechat),
):
    """获取报告详情"""
    try:
        db = get_mongo_db()
        doc = await db["analysis_reports"].find_one({
            "$or": [{"analysis_id": report_id}, {"task_id": report_id}]
        })

        if not doc:
            raise HTTPException(status_code=404, detail="报告不存在")

        return {
            "success": True,
            "data": {
                "analysis_id": doc.get("analysis_id", ""),
                "stock_symbol": doc.get("stock_symbol", ""),
                "stock_name": doc.get("stock_name", ""),
                "decision": doc.get("decision", {}),
                "summary": doc.get("summary", ""),
                "recommendation": doc.get("recommendation", ""),
                "confidence_score": doc.get("confidence_score", 0),
                "risk_level": doc.get("risk_level", "中等"),
                "key_points": doc.get("key_points", []),
                "reports": doc.get("reports", {}),
                "created_at": _fmt_time(doc.get("created_at")),
                "updated_at": _fmt_time(doc.get("updated_at")),
            },
            "message": "获取成功",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取报告详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/{report_id}/content/{module}")
async def get_report_module(
    report_id: str,
    module: str,
    user: dict = Depends(get_current_user_wechat),
):
    """获取报告特定模块内容"""
    try:
        db = get_mongo_db()
        doc = await db["analysis_reports"].find_one({
            "$or": [{"analysis_id": report_id}, {"task_id": report_id}]
        })

        if not doc:
            raise HTTPException(status_code=404, detail="报告不存在")

        reports = doc.get("reports", {})
        if module not in reports:
            raise HTTPException(status_code=404, detail=f"模块 {module} 不存在")

        return {
            "success": True,
            "data": {"module": module, "content": reports[module]},
            "message": "获取成功",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取模块内容失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
