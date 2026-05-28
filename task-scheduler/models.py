"""
任务调度服务 ORM 模型
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from shared.database import Base


def _uuid():
    return str(uuid.uuid4())


def _now():
    return datetime.now(timezone.utc).isoformat()


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String, nullable=False)
    target_url = Column(String, nullable=False)
    status = Column(String, nullable=False, default="CREATED")
    error_message = Column(Text, nullable=True)
    created_at = Column(String, nullable=False, default=_now)
    updated_at = Column(String, nullable=False, default=_now)

    steps = relationship("TaskStep", back_populates="task", order_by="TaskStep.created_at")


class TaskStep(Base):
    __tablename__ = "task_steps"

    id = Column(String, primary_key=True, default=_uuid)
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False)
    step_type = Column(String, nullable=False)  # SCAN, PLAN, EXECUTE
    service_name = Column(String, nullable=False)
    external_id = Column(String, nullable=True)  # 下游服务返回的 ID
    status = Column(String, nullable=False, default="PENDING")
    result_summary = Column(Text, nullable=True)
    created_at = Column(String, nullable=False, default=_now)
    updated_at = Column(String, nullable=False, default=_now)

    task = relationship("Task", back_populates="steps")
