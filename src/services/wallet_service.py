"""
Сервис кошелька пользователя.

Отвечает за:
- Пополнение баланса (admin)
- Списание средств за LLM запросы
- Историю транзакций
- Расчёт стоимости по токенам и цене модели
"""
from __future__ import annotations

import logging
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.orm_models import UserORM, UserTransactionORM

logger = logging.getLogger(__name__)

_CREDIT = "credit"
_DEBIT = "debit"


async def get_wallet(db: AsyncSession, user_id: str) -> dict[str, Any]:
    """Get user balance + recent transactions."""
    user = await db.get(UserORM, user_id)
    if not user:
        return {"balance": 0.0, "transactions": []}

    result = await db.execute(
        select(UserTransactionORM)
        .where(UserTransactionORM.user_id == user_id)
        .order_by(UserTransactionORM.created_at.desc())
        .limit(50)
    )
    txs = result.scalars().all()

    return {
        "balance": float(user.balance) if user.balance else 0.0,
        "transactions": [
            {
                "id": tx.id,
                "amount": float(tx.amount),
                "type": tx.type,
                "description": tx.description,
                "reference_id": tx.reference_id,
                "created_at": tx.created_at.isoformat() if tx.created_at else None,
            }
            for tx in txs
        ],
    }


async def top_up(
    db: AsyncSession,
    user_id: str,
    amount: float,
    description: str = "Пополнение баланса",
) -> dict[str, Any]:
    """Admin top-up: add credit to user balance."""
    if amount <= 0:
        raise ValueError("Сумма пополнения должна быть положительной")

    tx = UserTransactionORM(
        id=str(uuid.uuid4()),
        user_id=user_id,
        amount=amount,
        type=_CREDIT,
        description=description,
    )
    db.add(tx)

    await db.execute(
        text("UPDATE users SET balance = balance + :amount WHERE id = :user_id"),
        {"amount": str(amount), "user_id": user_id},
    )
    await db.flush()

    return {
        "transaction_id": tx.id,
        "amount": amount,
        "type": _CREDIT,
        "description": description,
    }


async def deduct_analysis_cost(
    db: AsyncSession,
    user_id: str,
    amount: float,
    model_id: str,
    result_id: str,
) -> dict[str, Any] | None:
    """Deduct cost from user balance after LLM analysis."""
    if amount <= 0:
        return None

    # Get current balance
    user = await db.get(UserORM, user_id)
    if not user:
        return None

    current_balance = float(user.balance) if user.balance else 0.0
    if current_balance < amount:
        # Allow going negative (overdraft) — deduct what we can
        logger.warning(
            "[wallet] user=%s insufficient balance: have %.2f, need %.2f",
            user_id, current_balance, amount,
        )

    tx = UserTransactionORM(
        id=str(uuid.uuid4()),
        user_id=user_id,
        amount=amount,
        type=_DEBIT,
        description=f"Анализ: {model_id}",
        reference_id=result_id,
    )
    db.add(tx)

    await db.execute(
        text("UPDATE users SET balance = balance - :amount WHERE id = :user_id"),
        {"amount": str(amount), "user_id": user_id},
    )
    await db.flush()

    return {
        "transaction_id": tx.id,
        "amount": amount,
        "type": _DEBIT,
        "description": f"Анализ: {model_id}",
        "balance_after": float(current_balance - amount),
    }


def estimate_cost(
    tokens_used: int,
    pricing_prompt: float | None,
    pricing_completion: float | None,
) -> float:
    """Estimate LLM cost from token usage × model pricing (per 1M tokens)."""
    if not pricing_prompt and not pricing_completion:
        return 0.0
    pp = pricing_prompt or 0.0
    pc = pricing_completion or 0.0
    # Assume 50/50 split for simplicity
    total = tokens_used * (pp + pc) / 2 / 1_000_000
    return round(total, 4)
