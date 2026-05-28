"""
任务调度服务 — 核心业务逻辑
负责工作流编排：扫描 → 规划 → 执行 → 报告
"""
import asyncio
import logging
from datetime import datetime, timezone

from shared.service_client import ServiceClient
from shared.models import EndpointInfo, TestCaseInfo

from . import config
from .models import Task, TaskStep

logger = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc).isoformat()


class TaskService:
    """任务管理 + 工作流编排"""

    def __init__(self, db_session_factory, service_client: ServiceClient):
        self._session_factory = db_session_factory
        self.client = service_client
        self._poll_interval = 1.0  # 轮询间隔（秒）
        self._max_poll = 120  # 最大轮询次数

    # ---- 任务 CRUD ----

    async def create_task(self, name: str, target_url: str) -> Task:
        """创建新任务"""
        async with self._session_factory() as session:
            task = Task(name=name, target_url=target_url)
            session.add(task)
            await session.commit()
            await session.refresh(task)
            # 预创建三个阶段的 step 记录
            for step_type, svc in [
                ("SCAN", "api-scanner"),
                ("PLAN", "ai-planner"),
                ("EXECUTE", "test-executor"),
            ]:
                step = TaskStep(
                    task_id=task.id,
                    step_type=step_type,
                    service_name=svc,
                )
                session.add(step)
            await session.commit()
            return task

    async def list_tasks(self, limit: int = 20, offset: int = 0) -> list[Task]:
        """分页查询任务列表"""
        async with self._session_factory() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(Task).order_by(Task.created_at.desc()).limit(limit).offset(offset)
            )
            return list(result.scalars().all())

    async def get_task(self, task_id: str) -> Task | None:
        """查询单个任务"""
        async with self._session_factory() as session:
            from sqlalchemy import select
            from sqlalchemy.orm import selectinload
            result = await session.execute(
                select(Task)
                .options(selectinload(Task.steps))
                .where(Task.id == task_id)
            )
            return result.scalar_one_or_none()

    async def get_task_report(self, task_id: str) -> dict | None:
        """代理获取测试报告"""
        try:
            resp = await self.client.get(
                "test-executor", f"/api/v1/reports/{task_id}"
            )
            return resp.json()
        except Exception as e:
            logger.error(f"获取报告失败: {e}")
            return None

    # ---- 工作流编排 ----

    async def run_workflow(self, task_id: str):
        """启动完整自动化测试流程"""
        task = await self.get_task(task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")

        try:
            # Step 1: 扫描接口
            await self._update_task_status(task_id, "SCANNING")
            endpoints = await self._run_scan(task_id, task.target_url)
            await self._update_step(task_id, "SCAN", "SUCCESS", f"发现 {len(endpoints)} 个接口")

            # Step 2: AI 生成测试用例
            await self._update_task_status(task_id, "PLANNING")
            test_cases = await self._run_plan(task_id, endpoints)
            await self._update_step(task_id, "PLAN", "SUCCESS", f"生成 {len(test_cases)} 条用例")

            # Step 3: 执行测试
            await self._update_task_status(task_id, "EXECUTING")
            result = await self._run_execute(task_id, test_cases)
            await self._update_step(task_id, "EXECUTE", "SUCCESS", result.get("summary", ""))

            # 完成
            await self._update_task_status(task_id, "COMPLETED")

        except Exception as e:
            logger.error(f"工作流失败: {e}")
            await self._update_task_status(task_id, "FAILED", str(e))

    async def _run_scan(self, task_id: str, target_url: str) -> list[dict]:
        """Step 1: 调用接口扫描服务"""
        resp = await self.client.post(
            "api-scanner",
            "/api/v1/scan",
            json={"task_id": task_id, "target_url": target_url},
        )
        scan_id = resp.json()["scan_id"]

        # 更新 step 的 external_id
        await self._set_step_external_id(task_id, "SCAN", scan_id)

        # 轮询等待扫描完成
        await self._poll_until(
            "api-scanner",
            f"/api/v1/scan/{scan_id}",
            lambda data: data.get("status") in ("SUCCESS", "FAILED"),
        )

        # 获取扫描结果
        resp = await self.client.get(
            "api-scanner", f"/api/v1/scan/{scan_id}/endpoints"
        )
        return resp.json()["endpoints"]

    async def _run_plan(self, task_id: str, endpoints: list[dict]) -> list[dict]:
        """Step 2: 调用 AI 规划服务"""
        resp = await self.client.post(
            "ai-planner",
            "/api/v1/plans",
            json={"task_id": task_id, "endpoints": endpoints},
        )
        plan_id = resp.json()["plan_id"]

        await self._set_step_external_id(task_id, "PLAN", plan_id)

        await self._poll_until(
            "ai-planner",
            f"/api/v1/plans/{plan_id}",
            lambda data: data.get("status") in ("SUCCESS", "FAILED"),
        )

        resp = await self.client.get("ai-planner", f"/api/v1/plans/{plan_id}")
        return resp.json()["test_cases"]

    async def _run_execute(self, task_id: str, test_cases: list[dict]) -> dict:
        """Step 3: 调用测试执行服务"""
        task = await self.get_task(task_id)
        resp = await self.client.post(
            "test-executor",
            "/api/v1/execute",
            json={
                "task_id": task_id,
                "test_cases": test_cases,
                "target_url": task.target_url,
            },
        )
        execution_id = resp.json()["execution_id"]

        await self._set_step_external_id(task_id, "EXECUTE", execution_id)

        await self._poll_until(
            "test-executor",
            f"/api/v1/execute/{execution_id}",
            lambda data: data.get("status") in ("SUCCESS", "PARTIAL_FAIL", "FAILED"),
        )

        resp = await self.client.get(
            "test-executor", f"/api/v1/execute/{execution_id}"
        )
        return resp.json()

    # ---- 轮询工具 ----

    async def _poll_until(self, service: str, path: str, done_check) -> dict:
        """轮询等待下游服务完成"""
        for _ in range(self._max_poll):
            try:
                resp = await self.client.get(service, path)
                data = resp.json()
                if done_check(data):
                    return data
            except Exception as e:
                logger.warning(f"轮询 {service}{path} 出错: {e}")
            await asyncio.sleep(self._poll_interval)
        raise TimeoutError(f"等待 {service} 超时")

    # ---- 状态更新 ----

    async def _update_task_status(self, task_id: str, status: str, error: str | None = None):
        async with self._session_factory() as session:
            from sqlalchemy import select
            result = await session.execute(select(Task).where(Task.id == task_id))
            task = result.scalar_one_or_none()
            if task:
                task.status = status
                task.error_message = error
                task.updated_at = _now()
                await session.commit()

    async def _update_step(self, task_id: str, step_type: str, status: str, summary: str = ""):
        async with self._session_factory() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(TaskStep).where(
                    TaskStep.task_id == task_id,
                    TaskStep.step_type == step_type,
                )
            )
            step = result.scalar_one_or_none()
            if step:
                step.status = status
                step.result_summary = summary
                step.updated_at = _now()
                await session.commit()

    async def _set_step_external_id(self, task_id: str, step_type: str, external_id: str):
        async with self._session_factory() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(TaskStep).where(
                    TaskStep.task_id == task_id,
                    TaskStep.step_type == step_type,
                )
            )
            step = result.scalar_one_or_none()
            if step:
                step.external_id = external_id
                step.status = "RUNNING"
                step.updated_at = _now()
                await session.commit()
