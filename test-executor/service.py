"""
测试执行与报告服务 — 核心业务逻辑
"""
import json
import logging
import time
from datetime import datetime, timezone

import httpx

from .models import Execution, ExecutionResult, Report
from .ai_validator import AIValidator
from .report_generator import ReportGenerator
from . import config

logger = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc).isoformat()


class ExecutorService:

    def __init__(self, db_session_factory):
        self._session_factory = db_session_factory
        self._validator = AIValidator()
        self._report_gen = ReportGenerator()
        self._http_client = httpx.AsyncClient(timeout=config.REQUEST_TIMEOUT, follow_redirects=True)

    async def create_execution(self, task_id: str) -> str:
        """创建执行记录，返回 execution_id"""
        async with self._session_factory() as session:
            execution = Execution(task_id=task_id, status="RUNNING")
            session.add(execution)
            await session.commit()
            return execution.id

    async def run_execute(self, execution_id: str, task_id: str, test_cases: list[dict], target_url: str):
        """后台执行测试用例集"""
        target = target_url.rstrip("/")
        results = []

        try:
            for i, case in enumerate(test_cases):
                logger.info(f"执行用例 {i+1}/{len(test_cases)}: {case.get('title', '')}")
                result = await self._execute_one(execution_id, case, target)
                results.append(result)

            # AI 批量校验
            validations = await self._validator.validate_batch(results)
            for result, validation in zip(results, validations):
                passed = validation.get("passed", False)
                result["ai_validation"] = validation
                result["status"] = "PASS" if passed else "FAIL"
                await self._update_result_status(result["result_id"], result["status"], validation)

            # 生成报告
            await self._generate_report(task_id, execution_id, results)

            # 更新执行状态
            await self._update_execution_status(execution_id, results)

        except Exception as e:
            logger.error(f"测试执行失败: {e}")
            await self._set_execution_status(execution_id, "FAILED")

    async def get_execution(self, execution_id: str) -> dict | None:
        """获取执行记录及结果"""
        async with self._session_factory() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(Execution).where(Execution.id == execution_id)
            )
            execution = result.scalar_one_or_none()
            if not execution:
                return None

            result = await session.execute(
                select(ExecutionResult).where(ExecutionResult.execution_id == execution_id)
            )
            results = result.scalars().all()

            return {
                "execution_id": execution.id,
                "task_id": execution.task_id,
                "status": execution.status,
                "created_at": execution.created_at,
                "results": [
                    {
                        "result_id": r.id,
                        "test_case_id": r.test_case_id,
                        "method": r.method,
                        "path": r.path,
                        "response_status": r.response_status,
                        "response_time_ms": r.response_time_ms,
                        "status": r.status,
                        "ai_validation": json.loads(r.ai_validation) if r.ai_validation else None,
                    }
                    for r in results
                ],
            }

    async def get_report(self, task_id: str) -> dict | None:
        """获取测试报告"""
        async with self._session_factory() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(Report).where(Report.task_id == task_id)
            )
            report = result.scalar_one_or_none()
            if not report:
                return None
            return {
                "task_id": report.task_id,
                "execution_id": report.execution_id,
                "total_cases": report.total_cases,
                "passed": report.passed,
                "failed": report.failed,
                "error": report.error,
                "pass_rate": report.pass_rate,
                "summary": json.loads(report.summary) if report.summary else {},
                "html_content": report.html_content,
                "created_at": report.created_at,
            }

    # ---- 内部方法 ----

    def _substitute_path_params(self, path: str, params: dict) -> str:
        """替换路径中的 {param} 占位符为实际值"""
        import re
        query = params.get("query", {})
        body = params.get("body", {}) or {}
        resolved = path
        for m in re.finditer(r"\{(\w+)\}", path):
            key = m.group(1)
            # 优先从 query 找，再 body，最后默认值
            val = query.get(key, body.get(key, f"1"))
            resolved = resolved.replace(f"{{{key}}}", str(val))
        return resolved

    async def _execute_one(
        self, execution_id: str, case: dict, target_url: str
    ) -> dict:
        """执行单条测试用例"""
        params = case.get("request_params", {})
        method = case.get("method", "GET")
        path = case.get("path", "/")
        path = self._substitute_path_params(path, params)

        url = f"{target_url}{path}"
        query = {k: v for k, v in params.get("query", {}).items()}
        headers = params.get("headers", {})
        body = params.get("body")

        request_detail = {
            "method": method,
            "url": url,
            "query": query,
            "headers": headers,
            "body": body,
        }

        start_time = time.time()
        try:
            resp = await self._http_client.request(
                method, url, params=query, headers=headers, json=body,
            )
            response_status = resp.status_code
            response_time_ms = int((time.time() - start_time) * 1000)
            try:
                response_body = resp.json()
            except Exception:
                response_body = resp.text
        except Exception as e:
            response_status = 0
            response_time_ms = int((time.time() - start_time) * 1000)
            response_body = str(e)

        # 保存到数据库
        async with self._session_factory() as session:
            er = ExecutionResult(
                execution_id=execution_id,
                test_case_id=case.get("case_id", ""),
                method=method,
                path=path,
                request_detail=json.dumps(request_detail, ensure_ascii=False),
                response_status=response_status,
                response_body=json.dumps(response_body, ensure_ascii=False) if isinstance(response_body, (dict, list)) else str(response_body),
                response_time_ms=response_time_ms,
                status="PENDING",
                executed_at=_now(),
            )
            session.add(er)
            await session.commit()
            result_id = er.id

        return {
            "result_id": result_id,
            "test_case": case,
            "method": method,
            "path": path,
            "response_status": response_status,
            "response_body": response_body,
            "response_time_ms": response_time_ms,
            "ai_validation": None,
            "status": "PENDING",
        }

    async def _update_result_status(self, result_id: str, status: str, validation: dict):
        """更新执行结果的状态"""
        async with self._session_factory() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(ExecutionResult).where(ExecutionResult.id == result_id)
            )
            er = result.scalar_one_or_none()
            if er:
                er.status = status
                er.ai_validation = json.dumps(validation, ensure_ascii=False)
                await session.commit()

    async def _generate_report(
        self, task_id: str, execution_id: str, results: list[dict]
    ):
        """生成并保存报告"""
        report_data = self._report_gen.generate(task_id, execution_id, results)

        async with self._session_factory() as session:
            existing = await session.execute(
                __import__("sqlalchemy").select(Report).where(Report.task_id == task_id)
            )
            existing = existing.scalar_one_or_none()

            if existing:
                existing.total_cases = report_data["total_cases"]
                existing.passed = report_data["passed"]
                existing.failed = report_data["failed"]
                existing.error = report_data["error"]
                existing.pass_rate = report_data["pass_rate"]
                existing.summary = report_data["summary"]
                existing.html_content = report_data["html_content"]
            else:
                report = Report(
                    task_id=task_id,
                    execution_id=execution_id,
                    total_cases=report_data["total_cases"],
                    passed=report_data["passed"],
                    failed=report_data["failed"],
                    error=report_data["error"],
                    pass_rate=report_data["pass_rate"],
                    summary=report_data["summary"],
                    html_content=report_data["html_content"],
                )
                session.add(report)
            await session.commit()

    async def _update_execution_status(self, execution_id: str, results: list[dict]):
        """根据执行结果更新状态"""
        failed_count = sum(1 for r in results if r.get("status") == "FAIL")
        if failed_count == 0:
            await self._set_execution_status(execution_id, "SUCCESS")
        elif failed_count < len(results):
            await self._set_execution_status(execution_id, "PARTIAL_FAIL")
        else:
            await self._set_execution_status(execution_id, "FAILED")

    async def _set_execution_status(self, execution_id: str, status: str):
        async with self._session_factory() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(Execution).where(Execution.id == execution_id)
            )
            execution = result.scalar_one_or_none()
            if execution:
                execution.status = status
                execution.updated_at = _now()
                await session.commit()

    async def close(self):
        await self._http_client.aclose()
