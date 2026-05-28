"""
微服务调用客户端 — OpenFeign 的 Python 替代方案
基于 httpx + Nacos 服务发现，支持降级到静态配置
"""
import logging
import random
import httpx

from .nacos_client import NacosRegistry

logger = logging.getLogger(__name__)


class ServiceClient:
    """基于 Nacos 服务发现的 HTTP 客户端"""

    def __init__(
        self,
        registry: NacosRegistry | None = None,
        static_config: dict[str, str] | None = None,
        timeout: float = 30.0,
    ):
        self.registry = registry
        # 静态配置: {"api-scanner": "http://localhost:8081", ...}
        self.static_config = static_config or {}
        self._client = httpx.AsyncClient(timeout=timeout)

    async def _get_base_url(self, service_name: str) -> str:
        """获取服务地址，优先 Nacos 发现，失败时降级到静态配置"""
        # 尝试 Nacos 发现
        if self.registry:
            try:
                instances = await self.registry.discover(service_name)
                if instances:
                    healthy = [i for i in instances if i.get("healthy")]
                    if healthy:
                        instance = random.choice(healthy)
                        return f"http://{instance['ip']}:{instance['port']}"
            except Exception as e:
                logger.warning(f"Nacos 发现 {service_name} 失败: {e}，尝试静态配置")

        # 降级：静态配置
        if service_name in self.static_config:
            return self.static_config[service_name]

        raise RuntimeError(f"服务 {service_name} 不可用（Nacos 离线且无静态配置）")

    async def request(
        self,
        service_name: str,
        method: str,
        path: str,
        **kwargs,
    ) -> httpx.Response:
        """发送 HTTP 请求到指定微服务"""
        base_url = await self._get_base_url(service_name)
        url = f"{base_url}{path}"
        logger.info(f"调用 {service_name}: {method} {url}")
        resp = await self._client.request(method, url, **kwargs)
        resp.raise_for_status()
        return resp

    async def get(self, service_name: str, path: str, **kwargs) -> httpx.Response:
        return await self.request(service_name, "GET", path, **kwargs)

    async def post(self, service_name: str, path: str, **kwargs) -> httpx.Response:
        return await self.request(service_name, "POST", path, **kwargs)

    async def close(self):
        await self._client.aclose()
