"""
接口扫描服务配置 — Nacos Config 优先，环境变量降级
"""
import os
import logging

from shared.config_center import ConfigCenter

logger = logging.getLogger(__name__)

SERVICE_NAME = os.getenv("SERVICE_NAME", "api-scanner")
SERVICE_HOST = os.getenv("SERVICE_HOST", "127.0.0.1")
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8081"))
NACOS_SERVER = os.getenv("NACOS_SERVER", "127.0.0.1:8848")
NACOS_NAMESPACE = os.getenv("NACOS_NAMESPACE", "")


async def init_config():
    global SERVICE_NAME, SERVICE_HOST, SERVICE_PORT, NACOS_SERVER, NACOS_NAMESPACE
    cc = ConfigCenter(SERVICE_NAME, NACOS_SERVER, NACOS_NAMESPACE)
    try:
        remote = await cc.load()
        if remote:
            SERVICE_NAME = remote.get("SERVICE_NAME", SERVICE_NAME)
            SERVICE_HOST = remote.get("SERVICE_HOST", SERVICE_HOST)
            SERVICE_PORT = int(remote.get("SERVICE_PORT", SERVICE_PORT))
            NACOS_SERVER = remote.get("NACOS_SERVER", NACOS_SERVER)
            NACOS_NAMESPACE = remote.get("NACOS_NAMESPACE", NACOS_NAMESPACE)
            logger.info("配置从 Nacos Config 加载成功")
    except Exception as e:
        logger.warning(f"Nacos Config 加载失败: {e}，使用环境变量降级")
    finally:
        await cc.close()
