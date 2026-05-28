"""
接口扫描服务 ORM 模型
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, ForeignKey, Integer
from shared.database import Base


def _uuid():
    return str(uuid.uuid4())


def _now():
    return datetime.now(timezone.utc).isoformat()


class ScanRecord(Base):
    __tablename__ = "scan_records"

    id = Column(String, primary_key=True, default=_uuid)
    task_id = Column(String, nullable=False)
    target_url = Column(String, nullable=False)
    openapi_url = Column(String, nullable=True)
    status = Column(String, nullable=False, default="RUNNING")  # RUNNING, SUCCESS, FAILED
    error_message = Column(Text, nullable=True)
    endpoint_count = Column(Integer, default=0)
    created_at = Column(String, nullable=False, default=_now)
    updated_at = Column(String, nullable=False, default=_now)


class ApiEndpoint(Base):
    __tablename__ = "api_endpoints"

    id = Column(String, primary_key=True, default=_uuid)
    scan_record_id = Column(String, ForeignKey("scan_records.id"), nullable=False)
    method = Column(String, nullable=False)  # GET, POST, PUT, DELETE, PATCH
    path = Column(String, nullable=False)  # /api/v1/users/{id}
    summary = Column(Text, nullable=True)
    tags = Column(Text, nullable=True)  # JSON 数组
    parameters = Column(Text, nullable=True)  # JSON
    request_body = Column(Text, nullable=True)  # JSON
    responses = Column(Text, nullable=True)  # JSON
    created_at = Column(String, nullable=False, default=_now)
