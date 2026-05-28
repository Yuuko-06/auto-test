"""
接口扫描服务 API 路由
"""
import asyncio
import logging
from fastapi import APIRouter, HTTPException, Depends

from .service import ScannerService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")


def get_service() -> ScannerService:
    from .main import get_scanner_service
    return get_scanner_service()


@router.post("/scan")
async def start_scan(
    body: dict,
    svc: ScannerService = Depends(get_service),
):
    """启动接口扫描"""
    task_id = body.get("task_id")
    target_url = body.get("target_url")
    if not task_id or not target_url:
        raise HTTPException(400, "缺少 task_id 或 target_url")

    # 创建扫描记录，后台异步执行扫描
    scan_id = await svc.create_record(task_id, target_url)
    asyncio.create_task(svc.run_scan(scan_id, target_url))
    return {"scan_id": scan_id, "status": "RUNNING"}


@router.get("/scan/{scan_id}")
async def get_scan(scan_id: str, svc: ScannerService = Depends(get_service)):
    """查询扫描状态"""
    result = await svc.get_scan(scan_id)
    if not result:
        raise HTTPException(404, "扫描记录不存在")
    return result


@router.get("/scan/{scan_id}/endpoints")
async def get_endpoints(scan_id: str, svc: ScannerService = Depends(get_service)):
    """获取扫描到的接口列表"""
    endpoints = await svc.get_endpoints(scan_id)
    return {"scan_id": scan_id, "endpoints": endpoints, "count": len(endpoints)}

