"""
AI 测试规划服务 — 核心业务逻辑
"""
import json
import logging
from datetime import datetime, timezone

from .models import TestPlan, TestCase
from .ai_client import AIClient

logger = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc).isoformat()


class PlannerService:

    def __init__(self, db_session_factory):
        self._session_factory = db_session_factory
        self._ai_client = AIClient()

    async def create_plan(self, task_id: str, endpoints: list[dict]) -> str:
        """创建测试规划记录，返回 plan_id（不阻塞）"""
        async with self._session_factory() as session:
            plan = TestPlan(task_id=task_id, status="GENERATING")
            session.add(plan)
            await session.commit()
            return plan.id

    async def generate_cases(self, plan_id: str, endpoints: list[dict]):
        """后台执行 AI 生成测试用例（由 API 层用 asyncio.create_task 调用）"""
        try:
            test_cases = await self._ai_client.generate_test_cases(endpoints)
            await self._save_test_cases(plan_id, test_cases, endpoints)
            await self._update_plan_status(plan_id, "SUCCESS", total_cases=len(test_cases))
        except Exception as e:
            logger.error(f"生成测试用例失败: {e}")
            await self._update_plan_status(plan_id, "FAILED", error=str(e))

    async def get_plan(self, plan_id: str) -> dict | None:
        """获取测试规划及测试用例"""
        async with self._session_factory() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(TestPlan).where(TestPlan.id == plan_id)
            )
            plan = result.scalar_one_or_none()
            if not plan:
                return None

            result = await session.execute(
                select(TestCase).where(TestCase.plan_id == plan_id)
            )
            cases = result.scalars().all()

            return {
                "plan_id": plan.id,
                "task_id": plan.task_id,
                "status": plan.status,
                "total_cases": plan.total_cases,
                "error_message": plan.error_message,
                "created_at": plan.created_at,
                "test_cases": [
                    {
                        "case_id": tc.id,
                        "endpoint_id": tc.endpoint_id,
                        "case_type": tc.case_type,
                        "title": tc.title,
                        "description": tc.description,
                        "priority": tc.priority,
                        "method": tc.method,
                        "path": tc.path,
                        "request_params": json.loads(tc.request_params) if tc.request_params else {},
                        "expected_status": tc.expected_status,
                        "expected_body": json.loads(tc.expected_body) if tc.expected_body else None,
                    }
                    for tc in cases
                ],
            }

    async def _save_test_cases(
        self, plan_id: str, cases: list[dict], endpoints: list[dict]
    ):
        """保存测试用例到数据库"""
        # 构建 endpoint_id -> endpoint info 的映射
        ep_map = {ep.get("endpoint_id", ""): ep for ep in endpoints}

        async with self._session_factory() as session:
            for case in cases:
                endpoint_id = case.get("endpoint_id", "")
                ep_info = ep_map.get(endpoint_id, {})

                tc = TestCase(
                    plan_id=plan_id,
                    endpoint_id=endpoint_id,
                    case_type=case.get("case_type", "NORMAL"),
                    title=case.get("title", "未命名用例"),
                    description=case.get("description", ""),
                    priority=case.get("priority", "MEDIUM"),
                    method=ep_info.get("method", case.get("method", "GET")),
                    path=ep_info.get("path", case.get("path", "/")),
                    request_params=json.dumps(case.get("request_params", {}), ensure_ascii=False),
                    expected_status=case.get("expected_status", 200),
                    expected_body=json.dumps(case.get("expected_body"), ensure_ascii=False) if case.get("expected_body") else None,
                )
                session.add(tc)
            await session.commit()

    async def _update_plan_status(
        self, plan_id: str, status: str, total_cases: int = 0, error: str | None = None
    ):
        """更新规划状态"""
        async with self._session_factory() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(TestPlan).where(TestPlan.id == plan_id)
            )
            plan = result.scalar_one_or_none()
            if plan:
                plan.status = status
                plan.total_cases = total_cases
                plan.error_message = error
                plan.updated_at = _now()
                await session.commit()
