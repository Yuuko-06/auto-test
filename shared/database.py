"""
数据库基础模块
SQLAlchemy async engine + session 工厂，使用 aiosqlite 驱动
"""
import os
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

# Docker 环境用 /app/data，本地开发用 ./data
DATABASE_DIR = os.getenv("DATABASE_DIR", "./data")


class Base(DeclarativeBase):
    """ORM 声明基类"""
    pass


def create_engine(db_name: str):
    """创建异步 SQLite 引擎"""
    # 确保数据目录存在
    Path(DATABASE_DIR).mkdir(parents=True, exist_ok=True)
    url = f"sqlite+aiosqlite:///{DATABASE_DIR}/{db_name}.db"
    return create_async_engine(url, echo=False)


def create_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    """创建异步 session 工厂"""
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db(engine):
    """建表（所有 import 了 Base 的 ORM 模型）"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
