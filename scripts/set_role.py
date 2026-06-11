#!/usr/bin/env python
"""CLI-утилита для назначения роли пользователю.

Примеры:
    python scripts/set_role.py --email admin@example.com --role admin
    python scripts/set_role.py --email user@example.com --role user
    python scripts/set_role.py --list

Требует переменную DATABASE_URL (берётся из .env или окружения).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

# Чтобы импорты src.* работали из корня проекта
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()  # noqa: E402 - must load env vars before other imports

from sqlalchemy import select, update  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.db.orm_models import UserORM  # noqa: E402

VALID_ROLES = {"user", "admin"}


def get_engine():
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL не задана. Укажите в .env или переменных окружения.")
        sys.exit(1)
    return create_async_engine(url, echo=False)


async def list_users() -> None:
    engine = get_engine()
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        rows = (await session.execute(
            select(UserORM.id, UserORM.email, UserORM.display_name, UserORM.role, UserORM.is_active)
            .order_by(UserORM.created_at)
        )).all()

    if not rows:
        print("Пользователей нет.")
        return

    print(f"{'EMAIL':<35} {'NAME':<25} {'ROLE':<10} {'ACTIVE':<8} {'ID'}")
    print("-" * 115)
    for uid, email, name, role, active in rows:
        marker = "✓" if active else "✗"
        print(f"{email:<35} {name:<25} {role:<10} {marker:<8} {uid}")

    await engine.dispose()


async def set_role(email: str, role: str) -> None:
    engine = get_engine()
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    normalized = email.strip().lower()

    async with async_session() as session:
        user = (await session.execute(
            select(UserORM).where(UserORM.email == normalized)
        )).scalar_one_or_none()

        if user is None:
            print(f"ERROR: Пользователь '{email}' не найден.")
            await engine.dispose()
            sys.exit(1)

        old_role = user.role
        if old_role == role:
            print(f"Роль '{email}' уже '{role}', ничего не изменено.")
            await engine.dispose()
            return

        await session.execute(
            update(UserORM).where(UserORM.id == user.id).values(role=role)
        )
        await session.commit()
        print(f"OK: {email}  {old_role} → {role}")
        print("Пользователю нужно перелогиниться, чтобы получить JWT с новой ролью.")

    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Управление ролями пользователей RCA Analyzer")
    parser.add_argument("--email", type=str, help="Email пользователя")
    parser.add_argument("--role", type=str, choices=sorted(VALID_ROLES), help="Новая роль")
    parser.add_argument("--list", action="store_true", help="Показать всех пользователей")

    args = parser.parse_args()

    if args.list:
        asyncio.run(list_users())
        return

    if not args.email or not args.role:
        parser.error("Укажите --email и --role, или используйте --list")

    asyncio.run(set_role(args.email, args.role))


if __name__ == "__main__":
    main()
