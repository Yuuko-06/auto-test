"""
任务调度服务入口
"""
import sys
import logging
from pathlib import Path
from contextlib import asynccontextmanager

# 确保 task-scheduler.main 和 __main__ 指向同一模块
# 避免 python -m 运行时相对导入创建副本导致模块级变量不一致
if __name__ == "__main__" and __package__:
    sys.modules[__package__ + ".main"] = sys.modules["__main__"]
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from shared.database import create_engine, create_session_factory, init_db
from shared.nacos_client import NacosRegistry
from shared.service_client import ServiceClient

from . import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# 模块级变量，避免 app.state 依赖注入时序问题
_task_service = None
_service_client = None


def get_task_service():
    """获取 TaskService（供 api.py 依赖注入使用）"""
    assert _task_service is not None, "TaskService 尚未初始化"
    return _task_service


def get_service_client():
    """获取 ServiceClient（供 api.py 代理端点使用）"""
    assert _service_client is not None, "ServiceClient 尚未初始化"
    return _service_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _task_service, _service_client

    logger.info(f"启动 {config.SERVICE_NAME}，端口 {config.SERVICE_PORT}")

    # 配置中心（Nacos Config 优先，失败降级到环境变量）
    await config.init_config()

    # 数据库
    engine = create_engine("scheduler")
    session_factory = create_session_factory(engine)
    await init_db(engine)
    logger.info("数据库初始化完成")

    # 注册中心 + 服务客户端
    registry = NacosRegistry(
        server_addr=config.NACOS_SERVER,
        namespace=config.NACOS_NAMESPACE,
    )
    service_client = ServiceClient(
        registry=registry,
        static_config=config.STATIC_SERVICES,
        timeout=180.0,
    )

    # 先初始化 TaskService（不依赖 Nacos 注册结果）
    from .service import TaskService
    _task_service = TaskService(session_factory, service_client)
    _service_client = service_client
    logger.info("TaskService 初始化完成")

    # 再注册 Nacos（可能失败，不影响核心功能）
    await registry.register(config.SERVICE_NAME, config.SERVICE_HOST, config.SERVICE_PORT)
    await registry.start_heartbeat(config.SERVICE_NAME, config.SERVICE_HOST, config.SERVICE_PORT)

    # 兼容 app.state 访问
    app.state.task_service = _task_service
    app.state.registry = registry
    app.state.service_client = service_client
    app.state.engine = engine

    yield

    # 关闭阶段
    logger.info(f"关闭 {config.SERVICE_NAME}")
    registry.stop_heartbeat(config.SERVICE_NAME)
    await registry.deregister(config.SERVICE_NAME, config.SERVICE_HOST, config.SERVICE_PORT)
    await registry.close()
    await service_client.close()
    await engine.dispose()


app = FastAPI(title="任务调度服务", version="1.0.0", lifespan=lifespan)

# CORS（允许前端跨域访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "task-scheduler"}


# API 路由（先注册，优先级高于静态文件）
from .api import router
app.include_router(router)


# 前端页面
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)


@app.get("/")
async def index():
    """返回前端单页面"""
    return FileResponse(str(static_dir / "index.html"))


# 静态文件（JSON / 报告等）
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=config.SERVICE_PORT)
