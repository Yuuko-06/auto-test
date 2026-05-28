"""
跨服务共享的 Pydantic 数据模型
用于服务间调用的请求/响应序列化
"""
from pydantic import BaseModel, Field


# ---- 接口扫描相关 ----

class ParameterSchema(BaseModel):
    """接口参数"""
    name: str
    location: str  # query, path, header, body
    required: bool = False
    param_type: str = "string"  # string, integer, boolean 等
    description: str = ""


class EndpointInfo(BaseModel):
    """接口信息"""
    endpoint_id: str
    method: str  # GET, POST, PUT, DELETE, PATCH
    path: str
    summary: str = ""
    tags: list[str] = []
    parameters: list[ParameterSchema] = []
    request_body_schema: dict | None = None
    response_schemas: dict[str, dict] = {}  # status_code -> schema


# ---- 测试用例相关 ----

class TestCaseInfo(BaseModel):
    """测试用例"""
    case_id: str
    endpoint_id: str
    case_type: str  # NORMAL, ABNORMAL, BOUNDARY
    title: str
    description: str = ""
    priority: str = "MEDIUM"  # HIGH, MEDIUM, LOW
    method: str
    path: str
    request_params: dict = Field(default_factory=dict)  # {query, headers, body}
    expected_status: int = 200
    expected_body: dict | None = None


# ---- 执行结果相关 ----

class ExecutionResultInfo(BaseModel):
    """测试执行结果"""
    result_id: str
    test_case_id: str
    method: str
    path: str
    request_detail: dict | None = None
    response_status: int | None = None
    response_body: str | None = None
    response_time_ms: int = 0
    ai_validation: dict | None = None  # {passed, reason, issues}
    status: str = "PENDING"  # PENDING, PASS, FAIL, ERROR


# ---- 任务相关 ----

class TaskCreateRequest(BaseModel):
    """创建任务请求"""
    target_url: str = Field(..., description="被测系统的根地址")
    name: str | None = Field(None, description="任务名称")


class TaskCreateResponse(BaseModel):
    """创建任务响应"""
    task_id: str
    name: str
    target_url: str
    status: str
    created_at: str


class TaskStepInfo(BaseModel):
    """任务阶段信息"""
    step_type: str  # SCAN, PLAN, EXECUTE
    status: str  # PENDING, RUNNING, SUCCESS, FAILED
    result_summary: str | None = None


class TaskDetailResponse(BaseModel):
    """任务详情"""
    task_id: str
    name: str
    target_url: str
    status: str
    error_message: str | None = None
    steps: list[TaskStepInfo] = []
    created_at: str
    updated_at: str
