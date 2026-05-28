"""
AI 测试规划服务配置
"""
import os

SERVICE_NAME = os.getenv("SERVICE_NAME", "ai-planner")
SERVICE_HOST = os.getenv("SERVICE_HOST", "127.0.0.1")
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8082"))
NACOS_SERVER = os.getenv("NACOS_SERVER", "127.0.0.1:8848")
NACOS_NAMESPACE = os.getenv("NACOS_NAMESPACE", "")

# AI 配置
AI_PROVIDER = os.getenv("AI_PROVIDER", "openai")  # openai 或 claude
AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_MODEL = os.getenv("AI_MODEL", "gpt-4o")
AI_BASE_URL = os.getenv("AI_BASE_URL", "")  # 自定义 API 端点
