"""
AI 测试规划服务 ORM 模型
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, ForeignKey, Integer
from shared.database import Base


def _uuid():
    return str(uuid.uuid4())


def _now():
    return datetime.now(timezone.utc).isoformat()


class TestPlan(Base):
    __tablename__ = "test_plans"

    id = Column(String, primary_key=True, default=_uuid)
    task_id = Column(String, nullable=False)
    status = Column(String, nullable=False, default="GENERATING")  # GENERATING, SUCCESS, FAILED
    total_cases = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(String, nullable=False, default=_now)
    updated_at = Column(String, nullable=False, default=_now)


class TestCase(Base):
    __tablename__ = "test_cases"

    id = Column(String, primary_key=True, default=_uuid)
    plan_id = Column(String, ForeignKey("test_plans.id"), nullable=False)
    endpoint_id = Column(String, nullable=False)
    case_type = Column(String, nullable=False)  # NORMAL, ABNORMAL, BOUNDARY
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(String, default="MEDIUM")  # HIGH, MEDIUM, LOW
    method = Column(String, nullable=False)
    path = Column(String, nullable=False)
    request_params = Column(Text, nullable=True)  # JSON: {query, headers, body}
    expected_status = Column(Integer, nullable=True)
    expected_body = Column(Text, nullable=True)  # JSON
    created_at = Column(String, nullable=False, default=_now)
