"""
任务调度服务配置
"""
import os

SERVICE_NAME = os.getenv("SERVICE_NAME", "task-scheduler")
SERVICE_HOST = os.getenv("SERVICE_HOST", "127.0.0.1")
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8080"))
NACOS_SERVER = os.getenv("NACOS_SERVER", "127.0.0.1:8848")
NACOS_NAMESPACE = os.getenv("NACOS_NAMESPACE", "")

# 静态服务地址（Nacos 不可用时的降级方案）
STATIC_SERVICES = {
    "api-scanner": os.getenv("SCANNER_URL", "http://127.0.0.1:8081"),
    "ai-planner": os.getenv("PLANNER_URL", "http://127.0.0.1:8082"),
    "test-executor": os.getenv("EXECUTOR_URL", "http://127.0.0.1:8083"),
}
