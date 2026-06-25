"""
FastAPI-роутер: кошелёк пользователя.

GET  /api/v1/user/wallet          — баланс + история транзакций
POST /api/v1/admin/wallet/topup   — пополнение баланса (admin)
"""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.models import UserInfo
from src.auth.service import get_current_user
from src.db.base import get_db
from src.services.wallet_service import deduct_analysis_cost, get_wallet, top_up

logger = logging.getLogger(__name__)

router = APIRouter(tags=["wallet"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[UserInfo, Depends(get_current_user)]


class TopUpRequest(BaseModel):
    user_id: str
    amount: float = Field(..., gt=0)
    description: str = "Пополнение баланса"


class WalletResponse(BaseModel):
    balance: float
    transactions: list[dict]


# ---------------------------------------------------------------------------
# GET /api/v1/user/wallet  — текущий баланс и история
# ---------------------------------------------------------------------------


@router.get("/api/v1/user/wallet", response_model=WalletResponse)
async def get_user_wallet(
    db: DbSession,
    current_user: CurrentUser,
):
    return await get_wallet(db, current_user.user_id)


# ---------------------------------------------------------------------------
# POST /api/v1/admin/wallet/topup  — пополнение (только admin)
# ---------------------------------------------------------------------------


@router.post("/api/v1/admin/wallet/topup", status_code=status.HTTP_201_CREATED)
async def admin_topup(
    body: TopUpRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Только администратор может пополнять баланс")
    try:
        result = await top_up(db, body.user_id, body.amount, body.description)
        await db.commit()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
