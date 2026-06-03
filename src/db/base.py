"""
Асинхронное подключение к PostgreSQL через SQLAlchemy.
Строка подключения читается из переменной DATABASE_URL.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL: str = os.environ["DATABASE_URL"]
# Пример: postgresql+asyncpg://rca:secret@db:5432/rca_analyzer

engine = create_async_engine(
    DATABASE_URL,
    echo=False,          # True → печатает SQL в stdout
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,  # проверяет соединение перед выдачей из пула
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


class Base(DeclarativeBase):
    """Базовый класс для всех ORM-моделей."""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI Depends: выдаёт сессию и закрывает её после запроса."""
    async with AsyncSessionLocal() as session:
        yield session
