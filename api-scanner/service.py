"""
接口扫描服务 — 核心逻辑
OpenAPI 文档抓取与解析
"""
import json
import logging
from datetime import datetime, timezone

import httpx

from .models import ScanRecord, ApiEndpoint

logger = logging.getLogger(__name__)

# OpenAPI 文档可能的路径
OPENAPI_PATHS = [
    "/v3/api-docs",
    "/api-docs",
    "/swagger.json",
    "/swagger/v1/swagger.json",
    "/v2/api-docs",
    "/openapi.json",
]


def _now():
    return datetime.now(timezone.utc).isoformat()


class ScannerService:
    """接口扫描业务逻辑"""

    def __init__(self, db_session_factory):
        self._session_factory = db_session_factory

    async def create_record(self, task_id: str, target_url: str) -> str:
        """创建扫描记录，返回 scan_id"""
        async with self._session_factory() as session:
            record = ScanRecord(task_id=task_id, target_url=target_url)
            session.add(record)
            await session.commit()
            return record.id

    async def run_scan(self, scan_id: str, target_url: str):
        """执行扫描的实际逻辑（由 API 层用 asyncio.create_task 调用）"""
        await self._do_scan(scan_id, target_url)

    async def get_scan(self, scan_id: str) -> dict | None:
        """获取扫描记录"""
        async with self._session_factory() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(ScanRecord).where(ScanRecord.id == scan_id)
            )
            record = result.scalar_one_or_none()
            if not record:
                return None
            return {
                "scan_id": record.id,
                "task_id": record.task_id,
                "target_url": record.target_url,
                "openapi_url": record.openapi_url,
                "status": record.status,
                "endpoint_count": record.endpoint_count,
                "error_message": record.error_message,
                "created_at": record.created_at,
            }

    async def get_endpoints(self, scan_id: str) -> list[dict]:
        """获取扫描到的接口列表"""
        async with self._session_factory() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(ApiEndpoint).where(ApiEndpoint.scan_record_id == scan_id)
            )
            endpoints = result.scalars().all()
            return [
                {
                    "endpoint_id": ep.id,
                    "method": ep.method,
                    "path": ep.path,
                    "summary": ep.summary,
                    "tags": json.loads(ep.tags) if ep.tags else [],
                    "parameters": json.loads(ep.parameters) if ep.parameters else [],
                    "request_body_schema": json.loads(ep.request_body) if ep.request_body else None,
                    "response_schemas": json.loads(ep.responses) if ep.responses else {},
                }
                for ep in endpoints
            ]

    async def _do_scan(self, scan_id: str, target_url: str):
        """执行扫描的实际逻辑"""
        async with self._session_factory() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(ScanRecord).where(ScanRecord.id == scan_id)
            )
            record = result.scalar_one_or_none()
            if not record:
                return

            target = target_url.rstrip("/")

            # Docker 容器内 localhost 指向容器自身，需同时尝试 host.docker.internal
            import re
            targets = [target]
            if re.match(r"https?://(localhost|127\.0\.0\.1)[:/]", target):
                alt = re.sub(r"://(localhost|127\.0\.0\.1)", r"://host.docker.internal", target)
                targets.append(alt)

            # 探测 OpenAPI 文档地址
            openapi_url = None
            openapi_doc = None
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:

                async def _try_get(url):
                    nonlocal openapi_doc, openapi_url
                    try:
                        resp = await client.get(url)
                        if resp.status_code == 200 and resp.text.strip().startswith("{"):
                            openapi_doc = resp.json()
                            openapi_url = url
                            return True
                    except Exception:
                        pass
                    return False

                for base in targets:
                    # 如果 target_url 本身是 .json 结尾，直接尝试获取
                    if base.endswith(".json") or "/json" in base:
                        if await _try_get(base):
                            break

                    # 否则按常规路径探测
                    if not openapi_doc:
                        for path in OPENAPI_PATHS:
                            url = f"{base}{path}"
                            if await _try_get(url):
                                break
                    if openapi_doc:
                        break

            if not openapi_doc:
                record.status = "FAILED"
                record.error_message = f"无法从 {target} 获取 OpenAPI 文档，尝试了 {OPENAPI_PATHS}"
                record.updated_at = _now()
                await session.commit()
                return

            record.openapi_url = openapi_url

            # 解析 OpenAPI 文档
            try:
                endpoints = self._parse_openapi(openapi_doc, scan_id)
                record.endpoint_count = len(endpoints)
                record.status = "SUCCESS"

                # 批量插入接口
                for ep in endpoints:
                    session.add(ep)

            except Exception as e:
                logger.error(f"解析 OpenAPI 失败: {e}")
                record.status = "FAILED"
                record.error_message = f"解析 OpenAPI 文档失败: {e}"

            record.updated_at = _now()
            await session.commit()

    def _parse_openapi(self, doc: dict, scan_record_id: str) -> list[ApiEndpoint]:
        """解析 OpenAPI 文档，提取接口信息"""
        endpoints = []

        # 支持 OpenAPI 3.x 和 Swagger 2.0
        paths = doc.get("paths", {})
        if not paths:
            return endpoints

        for path, methods in paths.items():
            if not isinstance(methods, dict):
                continue
            for method, detail in methods.items():
                if method.upper() not in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                    continue
                if not isinstance(detail, dict):
                    continue

                # 提取参数
                parameters = []
                for param in detail.get("parameters", []):
                    schema = param.get("schema", {})
                    parameters.append({
                        "name": param.get("name", ""),
                        "location": param.get("in", "query"),
                        "required": param.get("required", False),
                        "param_type": schema.get("type", "string"),
                        "description": param.get("description", ""),
                    })

                # 提取 requestBody (OpenAPI 3.x)
                request_body = None
                rb = detail.get("requestBody", {})
                if rb and "content" in rb:
                    json_content = rb["content"].get("application/json", {})
                    request_body = json_content.get("schema")

                # 提取 responses
                response_schemas = {}
                for status, resp in detail.get("responses", {}).items():
                    content = resp.get("content", {})
                    json_content = (
                        content.get("application/json", {})
                        or content.get("*/*", {})
                    )
                    schema = json_content.get("schema")
                    if schema:
                        response_schemas[str(status)] = schema

                # 提取 tags
                tags = detail.get("tags", [])

                ep = ApiEndpoint(
                    scan_record_id=scan_record_id,
                    method=method.upper(),
                    path=path,
                    summary=detail.get("summary", detail.get("operationId", "")),
                    tags=json.dumps(tags, ensure_ascii=False),
                    parameters=json.dumps(parameters, ensure_ascii=False),
                    request_body=json.dumps(request_body, ensure_ascii=False) if request_body else None,
                    responses=json.dumps(response_schemas, ensure_ascii=False),
                )
                endpoints.append(ep)

        return endpoints
