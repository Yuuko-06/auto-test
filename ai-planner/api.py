"""
AI 测试规划服务 API 路由
"""
import asyncio
import logging
from fastapi import APIRouter, HTTPException, Depends

from .service import PlannerService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")


def get_service() -> PlannerService:
    from .main import get_planner_service
    return get_planner_service()


@router.post("/plans")
async def create_plan(
    body: dict,
    svc: PlannerService = Depends(get_service),
):
    """创建测试规划并同步生成用例"""
    task_id = body.get("task_id")
    endpoints = body.get("endpoints", [])
    if not task_id:
        raise HTTPException(400, "缺少 task_id")

    plan_id = await svc.create_plan(task_id, endpoints)
    # 同步等待 AI 生成完成（20个接口约需60-90秒）
    await svc.generate_cases(plan_id, endpoints)
    result = await svc.get_plan(plan_id)
    return result


@router.get("/plans/{plan_id}")
async def get_plan(plan_id: str, svc: PlannerService = Depends(get_service)):
    """获取测试规划及用例"""
    result = await svc.get_plan(plan_id)
    if not result:
        raise HTTPException(404, "测试规划不存在")
    return result


@router.get("/health")
async def health():
    return {"status": "ok", "service": "ai-planner"}
