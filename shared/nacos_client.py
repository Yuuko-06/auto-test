"""
Nacos 服务注册与发现客户端
基于 Nacos Open API 的轻量封装，替代 nacos-sdk-python
参考文档: https://nacos.io/docs/latest/guide/user/open-api/
"""
import asyncio
import logging
import httpx

logger = logging.getLogger(__name__)


class NacosRegistry:
    """Nacos 注册中心 HTTP API 封装"""

    def __init__(
        self,
        server_addr: str = "127.0.0.1:8848",
        namespace: str = "",
        group: str = "DEFAULT_GROUP",
    ):
        self.server = server_addr.rstrip("/")
        self.namespace = namespace
        self.group = group
        self._client = httpx.AsyncClient(timeout=10.0)
        self._beat_tasks: dict[str, asyncio.Task] = {}

    # ---- 服务注册与注销 ----

    async def register(self, service_name: str, ip: str, port: int) -> bool:
        """注册服务实例到 Nacos"""
        url = f"http://{self.server}/nacos/v1/ns/instance"
        params = {
            "serviceName": service_name,
            "ip": ip,
            "port": port,
            "namespaceId": self.namespace,
            "groupName": self.group,
        }
        try:
            resp = await self._client.post(url, params=params)
            if resp.text == "ok":
                logger.info(f"服务 {service_name} 注册成功 ({ip}:{port})")
                return True
            logger.warning(f"服务 {service_name} 注册返回非预期: {resp.text}")
            return False
        except Exception as e:
            logger.error(f"服务 {service_name} 注册失败: {e}")
            return False

    async def deregister(self, service_name: str, ip: str, port: int) -> bool:
        """注销服务实例"""
        url = f"http://{self.server}/nacos/v1/ns/instance"
        params = {
            "serviceName": service_name,
            "ip": ip,
            "port": port,
            "namespaceId": self.namespace,
            "groupName": self.group,
        }
        try:
            resp = await self._client.delete(url, params=params)
            if resp.text == "ok":
                logger.info(f"服务 {service_name} 注销成功 ({ip}:{port})")
                return True
            return False
        except Exception as e:
            logger.error(f"服务 {service_name} 注销失败: {e}")
            return False

    # ---- 服务发现 ----

    async def discover(self, service_name: str) -> list[dict]:
        """获取服务的健康实例列表"""
        url = f"http://{self.server}/nacos/v1/ns/instance/list"
        params = {
            "serviceName": service_name,
            "namespaceId": self.namespace,
            "groupName": self.group,
            "healthyOnly": True,
        }
        try:
            resp = await self._client.get(url, params=params)
            data = resp.json()
            hosts = data.get("hosts", [])
            return [
                {
                    "ip": h["ip"],
                    "port": h["port"],
                    "healthy": h.get("healthy", True),
                    "weight": h.get("weight", 1.0),
                }
                for h in hosts
            ]
        except Exception as e:
            logger.error(f"服务发现失败 {service_name}: {e}")
            return []

    # ---- 心跳 ----

    async def send_heartbeat(self, service_name: str, ip: str, port: int) -> bool:
        """发送心跳"""
        url = f"http://{self.server}/nacos/v1/ns/instance/beat"
        params = {
            "serviceName": service_name,
            "ip": ip,
            "port": port,
            "namespaceId": self.namespace,
            "groupName": self.group,
        }
        try:
            resp = await self._client.put(url, params=params)
            return resp.status_code == 200
        except Exception:
            return False

    async def start_heartbeat(
        self, service_name: str, ip: str, port: int, interval: int = 5
    ):
        """启动后台心跳任务（每 interval 秒发送一次）"""
        async def _beat():
            while True:
                await asyncio.sleep(interval)
                ok = await self.send_heartbeat(service_name, ip, port)
                if not ok:
                    # 心跳失败时尝试重新注册
                    logger.warning(f"心跳失败，尝试重新注册 {service_name}")
                    await self.register(service_name, ip, port)

        task = asyncio.create_task(_beat())
        self._beat_tasks[service_name] = task

    def stop_heartbeat(self, service_name: str):
        """停止心跳任务"""
        task = self._beat_tasks.pop(service_name, None)
        if task:
            task.cancel()

    # ---- 清理 ----

    async def close(self):
        """关闭 HTTP 客户端"""
        for task in self._beat_tasks.values():
            task.cancel()
        self._beat_tasks.clear()
        await self._client.aclose()


class NacosConfigClient:
    """Nacos 配置中心 HTTP API 封装"""

    def __init__(
        self,
        server_addr: str = "127.0.0.1:8848",
        namespace: str = "",
        group: str = "DEFAULT_GROUP",
    ):
        self.server = server_addr.rstrip("/")
        self.namespace = namespace
        self.group = group
        self._client = httpx.AsyncClient(timeout=10.0)

    async def get_config(self, data_id: str, group: str | None = None) -> str | None:
        """从 Nacos 拉取配置，返回配置文本；不存在返回 None"""
        url = f"http://{self.server}/nacos/v1/cs/configs"
        params = {
            "dataId": data_id,
            "group": group or self.group,
            "tenant": self.namespace,
        }
        try:
            resp = await self._client.get(url, params=params)
            if resp.status_code == 404:
                logger.warning(f"配置 {data_id} 不存在")
                return None
            resp.raise_for_status()
            logger.info(f"配置 {data_id} 拉取成功")
            return resp.text
        except Exception as e:
            logger.error(f"拉取配置 {data_id} 失败: {e}")
            return None

    async def publish_config(
        self,
        data_id: str,
        content: str,
        config_type: str = "json",
        group: str | None = None,
    ) -> bool:
        """发布配置到 Nacos"""
        url = f"http://{self.server}/nacos/v1/cs/configs"
        data = {
            "dataId": data_id,
            "group": group or self.group,
            "tenant": self.namespace,
            "content": content,
            "type": config_type,
        }
        try:
            resp = await self._client.post(url, data=data)
            if resp.text == "true":
                logger.info(f"配置 {data_id} 发布成功")
                return True
            logger.warning(f"配置 {data_id} 发布返回: {resp.text}")
            return False
        except Exception as e:
            logger.error(f"发布配置 {data_id} 失败: {e}")
            return False

    async def delete_config(self, data_id: str, group: str | None = None) -> bool:
        """删除 Nacos 配置"""
        url = f"http://{self.server}/nacos/v1/cs/configs"
        params = {
            "dataId": data_id,
            "group": group or self.group,
            "tenant": self.namespace,
        }
        try:
            resp = await self._client.delete(url, params=params)
            return resp.text == "true"
        except Exception as e:
            logger.error(f"删除配置 {data_id} 失败: {e}")
            return False

    async def close(self):
        await self._client.aclose()
