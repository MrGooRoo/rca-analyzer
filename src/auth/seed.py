"""Seed первого администратора из переменных окружения.

При старте приложения вызывается ``ensure_admin_exists()``.
Если задана ``ADMIN_EMAIL``, ищет пользователя с этим email и ставит ему
``role='admin'``. Если пользователь ещё не зарегистрирован — ничего не делает
(он получит роль admin при следующем запуске после регистрации).

Переменные:
    ADMIN_EMAIL  — email пользователя, который станет admin (опционально).
"""

from __future__ import annotations

import logging
import os

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.orm_models import UserORM

logger = logging.getLogger(__name__)


async def ensure_admin_exists(session: AsyncSession) -> None:
    """Промотить пользователя в admin, если задана ADMIN_EMAIL."""
    admin_email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    if not admin_email:
        return

    user = (
        await session.execute(select(UserORM).where(UserORM.email == admin_email))
    ).scalar_one_or_none()

    if user is None:
        logger.info(
            "[SEED] ADMIN_EMAIL='%s' задан, но пользователь ещё не зарегистрирован. "
            "Роль будет назначена после регистрации и перезапуска.",
            admin_email,
        )
        return

    if user.role == "admin":
        logger.debug("[SEED] Пользователь '%s' уже admin.", admin_email)
        return

    await session.execute(
        update(UserORM).where(UserORM.id == user.id).values(role="admin")
    )
    await session.commit()
    logger.info("[SEED] Пользователь '%s' назначен admin.", admin_email)
