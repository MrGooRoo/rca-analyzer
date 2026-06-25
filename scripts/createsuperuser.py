#!/usr/bin/env python
"""CLI-утилита для создания первого администратора.

Использование:
    python scripts/createsuperuser.py               # интерактивный режим
    python scripts/createsuperuser.py --email admin@example.com --password Str0ngP@ss!  # non-interactive

Требует DATABASE_URL в .env или окружении.
Безопасна при повторном запуске: если пользователь уже существует — отказаться.
"""
from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.auth.service import hash_password
from src.db.orm_models import UserORM


def get_engine():
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL не задана. Укажите в .env или переменных окружения.")
        sys.exit(1)
    return create_async_engine(url, echo=False)


async def create_superuser(email: str, password: str, display_name: str) -> None:
    engine = get_engine()
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    normalized_email = email.strip().lower()

    async with async_session() as session:
        existing = (
            await session.execute(
                select(UserORM).where(UserORM.email == normalized_email)
            )
        ).scalar_one_or_none()

        if existing:
            print(f"ERROR: Пользователь '{email}' уже существует (role={existing.role}).")
            print("Используйте scripts/set_role.py для смены роли.")
            await engine.dispose()
            sys.exit(1)

        user = UserORM(
            id=__import__("uuid").uuid4().hex[:36],
            email=normalized_email,
            display_name=display_name.strip() or email.split("@")[0],
            hashed_password=hash_password(password),
            role="admin",
            is_active=True,
        )
        session.add(user)
        await session.commit()
        print(f"✓ Суперадминистратор создан:")
        print(f"  Email:        {email}")
        print(f"  Display name: {user.display_name}")
        print(f"  Role:         admin")
        print(f"  User ID:      {user.id}")
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Создать первого администратора RCA Analyzer",
        epilog="Без аргументов запускается интерактивный режим."
    )
    parser.add_argument("--email", type=str, help="Email администратора")
    parser.add_argument("--password", type=str, help="Пароль (мин. 10 символов)")
    parser.add_argument("--display-name", type=str, help="Имя для отображения")
    parser.add_argument("--yes", action="store_true", help="Не запрашивать подтверждение")

    args = parser.parse_args()

    if args.email:
        email = args.email.strip().lower()
        password = args.password or getpass.getpass("Пароль: ")
        display_name = args.display_name or email.split("@")[0]
    else:
        # Интерактивный режим
        print("=== Создание суперадминистратора ===")
        email = input("Email: ").strip().lower()
        password = getpass.getpass("Пароль (мин. 10 символов): ")
        confirm = getpass.getpass("Пароль (ещё раз): ")
        if password != confirm:
            print("ERROR: Пароли не совпадают.")
            sys.exit(1)
        if len(password) < 10:
            print("ERROR: Пароль должен быть минимум 10 символов.")
            sys.exit(1)
        display_name = input("Имя (Enter = часть email до @): ").strip() or email.split("@")[0]

        print()
        print(f"Email:        {email}")
        print(f"Имя:          {display_name}")
        print(f"Роль:         admin")
        if not args.yes:
            ok = input("Всё верно? (y/N): ").strip().lower()
            if ok != "y":
                print("Отменено.")
                sys.exit(0)

    asyncio.run(create_superuser(email, password, display_name))


if __name__ == "__main__":
    main()
