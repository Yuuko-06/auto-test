"""共享库 — 自动加载项目根目录的 .env 文件"""
from pathlib import Path
from dotenv import load_dotenv

# 加载项目根目录的 .env（shared/ 的上层目录）
_env_path = Path(__file__).parent.parent / ".env"
load_dotenv(_env_path)
