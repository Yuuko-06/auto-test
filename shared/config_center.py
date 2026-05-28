"""
配置中心 — Nacos Config 优先，环境变量降级
"""
import json
import os
import logging

from .nacos_client import NacosConfigClient

logger = logging.getLogger(__name__)


class ConfigCenter:
    """统一配置加载：Nacos Config → 环境变量降级"""

    def __init__(
        self,
        service_name: str,
        nacos_server: str = "127.0.0.1:8848",
        namespace: str = "",
        group: str = "DEFAULT_GROUP",
    ):
        self.service_name = service_name
        self._nacos = NacosConfigClient(
            server_addr=nacos_server,
            namespace=namespace,
            group=group,
        )
        self._cache: dict[str, str] = {}

    async def load(self) -> dict:
        """加载本服务配置，返回 dict"""
        data_id = f"{self.service_name}.json"
        content = await self._nacos.get_config(data_id)
        if content:
            try:
                config = json.loads(content)
                logger.info(f"[{self.service_name}] 使用 Nacos Config 配置")
                return config
            except json.JSONDecodeError:
                logger.warning(f"[{self.service_name}] Nacos 配置格式错误，降级到环境变量")
        logger.info(f"[{self.service_name}] Nacos Config 不可用，使用环境变量降级")
        return {}

    def get(self, key: str, default: str = "") -> str:
        """读取单个配置项：缓存优先 → 环境变量 → 默认值"""
        if key in self._cache:
            return self._cache[key]
        value = os.getenv(key, default)
        self._cache[key] = value
        return value

    async def close(self):
        await self._nacos.close()
