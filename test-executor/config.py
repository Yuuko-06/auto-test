"""
测试执行与报告服务配置
"""
import os

SERVICE_NAME = os.getenv("SERVICE_NAME", "test-executor")
SERVICE_HOST = os.getenv("SERVICE_HOST", "127.0.0.1")
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8083"))
NACOS_SERVER = os.getenv("NACOS_SERVER", "127.0.0.1:8848")
NACOS_NAMESPACE = os.getenv("NACOS_NAMESPACE", "")

# AI 配置（用于结果校验）
AI_PROVIDER = os.getenv("AI_PROVIDER", "openai")
AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_MODEL = os.getenv("AI_MODEL", "gpt-4o")
AI_BASE_URL = os.getenv("AI_BASE_URL", "")

REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
