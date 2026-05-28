"""
AI 测试规划服务入口
"""
import sys
import logging
from contextlib import asynccontextmanager

if __name__ == "__main__" and __package__:
    sys.modules[__package__ + ".main"] = sys.modules["__main__"]
from fastapi import FastAPI

from shared.database import create_engine, create_session_factory, init_db
from shared.nacos_client import NacosRegistry

from . import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# 模块级变量，避免 app.state 依赖注入时序问题
_planner_service = None


def get_planner_service():
    """获取 PlannerService（供 api.py 依赖注入使用）"""
    assert _planner_service is not None, "PlannerService 尚未初始化"
    return _planner_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _planner_service

    logger.info(f"启动 {config.SERVICE_NAME}，端口 {config.SERVICE_PORT}")

    await config.init_config()

    engine = create_engine("planner")
    session_factory = create_session_factory(engine)
    await init_db(engine)
    logger.info("数据库初始化完成")

    registry = NacosRegistry(
        server_addr=config.NACOS_SERVER,
        namespace=config.NACOS_NAMESPACE,
    )

    # 先初始化业务服务
    from .service import PlannerService
    _planner_service = PlannerService(session_factory)
    logger.info("PlannerService 初始化完成")

    # 再注册 Nacos（失败不影响核心功能）
    await registry.register(config.SERVICE_NAME, config.SERVICE_HOST, config.SERVICE_PORT)
    await registry.start_heartbeat(config.SERVICE_NAME, config.SERVICE_HOST, config.SERVICE_PORT)

    # 兼容 app.state 访问
    app.state.planner_service = _planner_service
    app.state.registry = registry
    app.state.engine = engine

    yield

    logger.info(f"关闭 {config.SERVICE_NAME}")
    registry.stop_heartbeat(config.SERVICE_NAME)
    await registry.deregister(config.SERVICE_NAME, config.SERVICE_HOST, config.SERVICE_PORT)
    await registry.close()
    await engine.dispose()


app = FastAPI(title="AI测试规划服务", version="1.0.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ai-planner"}


from .api import router
app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=config.SERVICE_PORT)
