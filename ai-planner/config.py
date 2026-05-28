"""
AI 测试规划服务配置 — Nacos Config 优先，环境变量降级
"""
import os
import logging

from shared.config_center import ConfigCenter

logger = logging.getLogger(__name__)

SERVICE_NAME = os.getenv("SERVICE_NAME", "ai-planner")
SERVICE_HOST = os.getenv("SERVICE_HOST", "127.0.0.1")
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8082"))
NACOS_SERVER = os.getenv("NACOS_SERVER", "127.0.0.1:8848")
NACOS_NAMESPACE = os.getenv("NACOS_NAMESPACE", "")

# AI 配置
AI_PROVIDER = os.getenv("AI_PROVIDER", "openai")
AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_MODEL = os.getenv("AI_MODEL", "gpt-4o")
AI_BASE_URL = os.getenv("AI_BASE_URL", "")


async def init_config():
    global SERVICE_NAME, SERVICE_HOST, SERVICE_PORT, NACOS_SERVER, NACOS_NAMESPACE
    global AI_PROVIDER, AI_API_KEY, AI_MODEL, AI_BASE_URL
    cc = ConfigCenter(SERVICE_NAME, NACOS_SERVER, NACOS_NAMESPACE)
    try:
        remote = await cc.load()
        if remote:
            SERVICE_NAME = remote.get("SERVICE_NAME", SERVICE_NAME)
            SERVICE_HOST = remote.get("SERVICE_HOST", SERVICE_HOST)
            SERVICE_PORT = int(remote.get("SERVICE_PORT", SERVICE_PORT))
            NACOS_SERVER = remote.get("NACOS_SERVER", NACOS_SERVER)
            NACOS_NAMESPACE = remote.get("NACOS_NAMESPACE", NACOS_NAMESPACE)
            AI_PROVIDER = remote.get("AI_PROVIDER", AI_PROVIDER)
            AI_API_KEY = remote.get("AI_API_KEY", AI_API_KEY)
            AI_MODEL = remote.get("AI_MODEL", AI_MODEL)
            AI_BASE_URL = remote.get("AI_BASE_URL", AI_BASE_URL)
            logger.info("配置从 Nacos Config 加载成功")
    except Exception as e:
        logger.warning(f"Nacos Config 加载失败: {e}，使用环境变量降级")
    finally:
        await cc.close()
