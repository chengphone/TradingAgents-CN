"""
股票分析API路由（微信小程序版）
仅保留单股分析和任务状态查询
"""

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from typing import Optional, Dict, Any
import logging
import time

from app.routers.wechat_auth import get_current_user_wechat
from app.services.simple_analysis_service import get_simple_analysis_service
from app.core.cloudbase_client import get_mongo_db, check_and_increment_quota
from app.core.config import settings
from app.models.analysis import SingleAnalysisRequest

router = APIRouter()
logger = logging.getLogger("webapi")


@router.post("/single")
async def submit_single_analysis(
    request: SingleAnalysisRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user_wechat),
):
    """提交单股分析任务"""
    try:
        openid = user["openid"]

        # 获取股票代码
        symbol = request.get_symbol()
        if not symbol:
            raise HTTPException(status_code=400, detail="请提供股票代码 (symbol)")

        # 检查配额
        allowed, used = await check_and_increment_quota(
            openid, settings.WECHAT_DAILY_QUOTA
        )
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=f"今日分析配额已用完 ({settings.WECHAT_DAILY_QUOTA}次/天)",
            )

        analysis_service = get_simple_analysis_service()
        result = await analysis_service.create_analysis_task(openid, request)
        task_id = result["task_id"]

        async def run_analysis():
            try:
                service = get_simple_analysis_service()
                await service.execute_analysis_background(task_id, openid, request)
            except Exception as e:
                logger.error(f"分析任务失败: {task_id}, {e}", exc_info=True)

        background_tasks.add_task(run_analysis)

        return {
            "success": True,
            "data": {"task_id": task_id, "status": "pending"},
            "message": "分析任务已提交",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"提交分析失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{task_id}/status")
async def get_task_status(
    task_id: str,
    user: dict = Depends(get_current_user_wechat),
):
    """获取分析任务状态（增加用户权限过滤）"""
    try:
        openid = user["openid"]
        analysis_service = get_simple_analysis_service()
        result = await analysis_service.get_task_status(task_id)

        if result:
            return {"success": True, "data": result}

        # 兜底：从数据库查找（增加用户过滤）
        db = get_mongo_db()
        task = await db["analysis_tasks"].find_one({
            "task_id": task_id,
            "$or": [
                {"openid": openid},
                {"user_id": openid},
                {"user": openid}
            ]
        })
        if task:
            from datetime import datetime
            start_time = task.get("started_at") or task.get("created_at")
            elapsed = (
                (datetime.utcnow() - start_time).total_seconds()
                if start_time
                else 0
            )
            return {
                "success": True,
                "data": {
                    "task_id": task_id,
                    "status": task.get("status", "unknown"),
                    "progress": task.get("progress", 0),
                    "message": task.get("message", ""),
                    "symbol": task.get("symbol", ""),
                    "elapsed_time": elapsed,
                },
            }

        raise HTTPException(status_code=404, detail="任务不存在或无权访问")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{task_id}/result")
async def get_task_result(
    task_id: str,
    user: dict = Depends(get_current_user_wechat),
):
    """获取分析任务结果（增加用户权限过滤）"""
    try:
        openid = user["openid"]
        analysis_service = get_simple_analysis_service()
        task_status = await analysis_service.get_task_status(task_id)

        result_data = None

        if task_status and task_status.get("status") == "completed":
            result_data = task_status.get("result_data")

        if not result_data:
            db = get_mongo_db()
            # 增加用户过滤
            result_data = await db["analysis_reports"].find_one({
                "task_id": task_id,
                "$or": [
                    {"openid": openid},
                    {"user_id": openid},
                    {"user": openid}
                ]
            })

        if not result_data:
            raise HTTPException(status_code=404, detail="分析结果不存在或无权访问")

        return {
            "success": True,
            "data": {
                "analysis_id": result_data.get("analysis_id", ""),
                "symbol": result_data.get("stock_symbol") or result_data.get("symbol", ""),
                "decision": result_data.get("decision", {}),
                "summary": result_data.get("summary", ""),
                "recommendation": result_data.get("recommendation", ""),
                "confidence_score": result_data.get("confidence_score", 0),
                "risk_level": result_data.get("risk_level", "中等"),
                "key_points": result_data.get("key_points", []),
                "reports": result_data.get("reports", {}),
                "created_at": str(result_data.get("created_at", "")),
            },
            "message": "获取成功",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks")
async def list_user_tasks(
    user: dict = Depends(get_current_user_wechat),
    status: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """获取用户分析任务列表"""
    try:
        openid = user["openid"]
        db = get_mongo_db()

        query = {"openid": openid}
        if status:
            query["status"] = status

        tasks = []
        cursor = db["analysis_tasks"].find(query).sort("created_at", -1).limit(limit)
        async for doc in cursor:
            tasks.append({
                "task_id": doc.get("task_id", ""),
                "symbol": doc.get("symbol", ""),
                "status": doc.get("status", ""),
                "progress": doc.get("progress", 0),
                "created_at": str(doc.get("created_at", "")),
                "completed_at": str(doc.get("completed_at", "")),
            })

        total = await db["analysis_tasks"].count_documents(query)

        return {
            "success": True,
            "data": {"tasks": tasks, "total": total},
            "message": "获取成功",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_analysis_history(
    user: dict = Depends(get_current_user_wechat),
    symbol: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """获取用户分析历史"""
    try:
        openid = user["openid"]
        db = get_mongo_db()

        query = {"openid": openid}
        if symbol:
            query["stock_symbol"] = symbol

        tasks = []
        cursor = (
            db["analysis_reports"]
            .find(query)
            .sort("created_at", -1)
            .limit(page_size)
        )
        async for doc in cursor:
            tasks.append({
                "analysis_id": doc.get("analysis_id", ""),
                "symbol": doc.get("stock_symbol", ""),
                "stock_name": doc.get("stock_name", ""),
                "decision": doc.get("decision", {}),
                "summary": (doc.get("summary", "") or "")[:200],
                "created_at": str(doc.get("created_at", "")),
            })

        total = await db["analysis_reports"].count_documents(query)

        return {
            "success": True,
            "data": {
                "reports": tasks,
                "total": total,
                "page": page,
                "page_size": page_size,
            },
            "message": "获取成功",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
