"""
测试执行与报告服务 API 路由
"""
import asyncio
import logging
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import HTMLResponse

from .service import ExecutorService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")


def get_service() -> ExecutorService:
    from .main import get_executor_service
    return get_executor_service()


@router.post("/execute")
async def start_execute(
    body: dict,
    svc: ExecutorService = Depends(get_service),
):
    """启动测试执行"""
    task_id = body.get("task_id")
    test_cases = body.get("test_cases", [])
    target_url = body.get("target_url", "")
    if not task_id:
        raise HTTPException(400, "缺少 task_id")

    execution_id = await svc.execute(task_id, test_cases, target_url)
    return {"execution_id": execution_id, "status": "RUNNING"}


@router.get("/execute/{execution_id}")
async def get_execution(execution_id: str, svc: ExecutorService = Depends(get_service)):
    """查询执行状态"""
    result = await svc.get_execution(execution_id)
    if not result:
        raise HTTPException(404, "执行记录不存在")
    return result


@router.get("/reports/{task_id}")
async def get_report(task_id: str, svc: ExecutorService = Depends(get_service)):
    """获取测试报告（JSON）"""
    report = await svc.get_report(task_id)
    if not report:
        raise HTTPException(404, "报告不存在")
    return report


@router.get("/reports/{task_id}/download", response_class=HTMLResponse)
async def download_report(task_id: str, svc: ExecutorService = Depends(get_service)):
    """下载 HTML 格式报告"""
    report = await svc.get_report(task_id)
    if not report or not report.get("html_content"):
        raise HTTPException(404, "报告不存在")
    return HTMLResponse(content=report["html_content"])


@router.get("/health")
async def health():
    return {"status": "ok", "service": "test-executor"}
