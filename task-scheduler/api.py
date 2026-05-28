"""
任务调度服务 API 路由
包含任务管理 + 前端代理端点（按步骤调用下游服务）
"""
import logging
from fastapi import APIRouter, HTTPException, Depends

from shared.models import (
    TaskCreateRequest,
    TaskCreateResponse,
    TaskDetailResponse,
    TaskStepInfo,
)

from .service import TaskService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")


# ---- 依赖注入 ----

def get_service() -> TaskService:
    """获取 TaskService（模块级变量，避免 app.state 时序问题）"""
    from .main import get_task_service
    return get_task_service()


def get_client():
    """获取 ServiceClient（用于代理调用下游服务）"""
    from .main import get_service_client
    return get_service_client()


# ---- 任务管理 ----

@router.post("/tasks", response_model=TaskCreateResponse, status_code=201)
async def create_task(req: TaskCreateRequest, svc: TaskService = Depends(get_service)):
    """创建测试任务"""
    name = req.name or f"测试-{req.target_url}"
    task = await svc.create_task(name, req.target_url)
    return TaskCreateResponse(
        task_id=task.id,
        name=task.name,
        target_url=task.target_url,
        status=task.status,
        created_at=task.created_at,
    )


@router.get("/tasks", response_model=list[TaskCreateResponse])
async def list_tasks(
    limit: int = 20, offset: int = 0, svc: TaskService = Depends(get_service)
):
    """查询任务列表"""
    tasks = await svc.list_tasks(limit, offset)
    return [
        TaskCreateResponse(
            task_id=t.id, name=t.name, target_url=t.target_url,
            status=t.status, created_at=t.created_at,
        )
        for t in tasks
    ]


@router.get("/tasks/{task_id}", response_model=TaskDetailResponse)
async def get_task(task_id: str, svc: TaskService = Depends(get_service)):
    """查询任务详情"""
    task = await svc.get_task(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    return TaskDetailResponse(
        task_id=task.id,
        name=task.name,
        target_url=task.target_url,
        status=task.status,
        error_message=task.error_message,
        steps=[
            TaskStepInfo(
                step_type=s.step_type,
                status=s.status,
                result_summary=s.result_summary,
            )
            for s in (task.steps or [])
        ],
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


# ---- 代理端点：前端按步骤调用下游服务 ----

@router.post("/tasks/{task_id}/scan")
async def proxy_scan(task_id: str, body: dict, client=Depends(get_client)):
    """步骤1：启动接口扫描 → api-scanner:8081"""
    target_url = body.get("target_url", "")
    resp = await client.post(
        "api-scanner", "/api/v1/scan",
        json={"task_id": task_id, "target_url": target_url},
    )
    return resp.json()


@router.get("/tasks/{task_id}/scan-status")
async def proxy_scan_status(task_id: str, scan_id: str, client=Depends(get_client)):
    """查询扫描状态 → api-scanner"""
    resp = await client.get("api-scanner", f"/api/v1/scan/{scan_id}")
    return resp.json()


@router.get("/tasks/{task_id}/endpoints")
async def proxy_endpoints(task_id: str, scan_id: str, client=Depends(get_client)):
    """获取扫描到的接口列表 → api-scanner"""
    resp = await client.get("api-scanner", f"/api/v1/scan/{scan_id}/endpoints")
    return resp.json()


@router.post("/tasks/{task_id}/plan")
async def proxy_plan(task_id: str, body: dict, client=Depends(get_client)):
    """步骤2：AI 生成测试用例 → ai-planner:8082（同步等待，可能需 60-90 秒）"""
    endpoints = body.get("endpoints", [])
    resp = await client.post(
        "ai-planner", "/api/v1/plans",
        json={"task_id": task_id, "endpoints": endpoints},
        timeout=180.0,
    )
    return resp.json()


@router.post("/tasks/{task_id}/execute")
async def proxy_execute(task_id: str, body: dict, client=Depends(get_client)):
    """步骤3：启动测试执行 → test-executor:8083"""
    test_cases = body.get("test_cases", [])
    target_url = body.get("target_url", "")
    resp = await client.post(
        "test-executor", "/api/v1/execute",
        json={"task_id": task_id, "test_cases": test_cases, "target_url": target_url},
    )
    return resp.json()


@router.get("/tasks/{task_id}/execute-status")
async def proxy_execute_status(task_id: str, execution_id: str, client=Depends(get_client)):
    """查询执行状态 → test-executor"""
    resp = await client.get("test-executor", f"/api/v1/execute/{execution_id}")
    return resp.json()


@router.get("/tasks/{task_id}/report")
async def proxy_report(task_id: str, client=Depends(get_client)):
    """获取测试报告 → test-executor"""
    try:
        resp = await client.get("test-executor", f"/api/v1/reports/{task_id}")
        return resp.json()
    except Exception as e:
        logger.error(f"获取报告失败: {e}")
        raise HTTPException(404, "报告不存在或尚未生成")


@router.get("/health")
async def health():
    return {"status": "ok", "service": "task-scheduler"}
