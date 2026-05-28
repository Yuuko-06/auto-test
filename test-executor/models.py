"""
测试执行与报告服务 ORM 模型
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, ForeignKey, Integer, Float
from shared.database import Base


def _uuid():
    return str(uuid.uuid4())


def _now():
    return datetime.now(timezone.utc).isoformat()


class Execution(Base):
    __tablename__ = "executions"

    id = Column(String, primary_key=True, default=_uuid)
    task_id = Column(String, nullable=False)
    plan_id = Column(String, nullable=True)
    status = Column(String, nullable=False, default="RUNNING")  # RUNNING, SUCCESS, PARTIAL_FAIL, FAILED
    created_at = Column(String, nullable=False, default=_now)
    updated_at = Column(String, nullable=False, default=_now)


class ExecutionResult(Base):
    __tablename__ = "execution_results"

    id = Column(String, primary_key=True, default=_uuid)
    execution_id = Column(String, ForeignKey("executions.id"), nullable=False)
    test_case_id = Column(String, nullable=False)
    method = Column(String, nullable=False)
    path = Column(String, nullable=False)
    request_detail = Column(Text, nullable=True)  # JSON
    response_status = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    response_time_ms = Column(Integer, default=0)
    ai_validation = Column(Text, nullable=True)  # JSON: {passed, reason, issues}
    status = Column(String, nullable=False, default="PENDING")  # PENDING, PASS, FAIL, ERROR
    executed_at = Column(String, nullable=True)
    created_at = Column(String, nullable=False, default=_now)


class Report(Base):
    __tablename__ = "reports"

    id = Column(String, primary_key=True, default=_uuid)
    task_id = Column(String, nullable=False, unique=True)
    execution_id = Column(String, ForeignKey("executions.id"), nullable=False)
    total_cases = Column(Integer, default=0)
    passed = Column(Integer, default=0)
    failed = Column(Integer, default=0)
    error = Column(Integer, default=0)
    pass_rate = Column(Float, nullable=True)
    summary = Column(Text, nullable=True)  # JSON
    html_content = Column(Text, nullable=True)  # HTML 报告全文
    created_at = Column(String, nullable=False, default=_now)
