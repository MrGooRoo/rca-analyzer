"""
FastAPI-роутер: анализ инцидентов.

Защищённые эндпоинты требуют auth-cookie или Bearer-токен.
Результаты привязываются к user_id текущего пользователя.

Роли:
  - admin: видит, редактирует и удаляет любые результаты.
  - user:  видит и управляет только своими записями.
"""

from __future__ import annotations

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.models import UserInfo
from src.auth.service import get_current_user
from src.db.base import get_db
from src.db.repository import RCARepository
from src.domain.models import (
    AnalysisRequest,
    LLMResponseValidationError,
    MethodologyNotSupportedError,
    RCAResult,
)
from src.services.analysis_service import AnalysisService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["analysis"])
_service = AnalysisService()

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[UserInfo, Depends(get_current_user)]


def _check_owner_or_admin(result: RCAResult, current_user: UserInfo) -> None:
    """Проверить, что пользователь — владелец записи или admin."""
    if current_user.role == "admin":
        return
    if result.user_id and result.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Доступ запрещён")


# ---------------------------------------------------------------------------
# POST /api/v1/analyze
# ---------------------------------------------------------------------------

@router.post(
    "/analyze",
    response_model=RCAResult,
    status_code=status.HTTP_201_CREATED,
    summary="Запустить RCA-анализ инцидента",
)
async def analyze_incident(
    request: AnalysisRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> RCAResult:
    try:
        result = await _service.analyze(request)
    except MethodologyNotSupportedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMResponseValidationError as exc:
        logger.error("[API] LLM error: %s", exc)
        raise HTTPException(status_code=502, detail="LLM не вернул валидный ответ.") from exc

    repo = RCARepository(db)
    await repo.save_result(result, user_id=current_user.user_id)
    logger.info("[DB] saved result %s for user %s", result.result_id, current_user.user_id)

    result.user_id = current_user.user_id
    return result


# ---------------------------------------------------------------------------
# GET /api/v1/results/{result_id}
# ---------------------------------------------------------------------------

@router.get(
    "/results/{result_id}",
    response_model=RCAResult,
    summary="Получить результат анализа из БД",
)
async def get_result(
    result_id: str,
    db: DbSession,
    current_user: CurrentUser,
) -> RCAResult:
    repo = RCARepository(db)
    result = await repo.get_result(result_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Результат '{result_id}' не найден.")
    _check_owner_or_admin(result, current_user)
    return result


# ---------------------------------------------------------------------------
# GET /api/v1/results
# ---------------------------------------------------------------------------

@router.get(
    "/results",
    response_model=list[RCAResult],
    summary="Список результатов (admin — все, user — свои)",
)
async def list_results(
    db: DbSession,
    current_user: CurrentUser,
    incident_id: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[RCAResult]:
    repo = RCARepository(db)
    # Admin видит все результаты, обычный пользователь — только свои
    user_id_filter = None if current_user.role == "admin" else current_user.user_id
    return await repo.list_results(
        user_id=user_id_filter,
        incident_id=incident_id,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# DELETE /api/v1/results/{result_id}
# ---------------------------------------------------------------------------

@router.delete(
    "/results/{result_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить результат анализа",
)
async def delete_result(
    result_id: str,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    repo = RCARepository(db)
    result = await repo.get_result(result_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Результат '{result_id}' не найден.")
    _check_owner_or_admin(result, current_user)
    await repo.delete_result(result_id)


# ---------------------------------------------------------------------------
# PATCH /api/v1/results/{result_id}/recommendations/{rec_id}
# ---------------------------------------------------------------------------

class StatusUpdate(BaseModel):
    status: str


@router.patch(
    "/results/{result_id}/recommendations/{rec_id}",
    summary="Обновить статус рекомендации",
)
async def update_recommendation(
    result_id: str,
    rec_id: str,
    body: StatusUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    valid_statuses = {"open", "in_progress", "closed"}
    if body.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Статус должен быть: {valid_statuses}")

    repo = RCARepository(db)
    result = await repo.get_result(result_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Результат '{result_id}' не найден.")
    _check_owner_or_admin(result, current_user)

    updated = await repo.update_recommendation_status(result_id, rec_id, body.status)
    if not updated:
        raise HTTPException(status_code=404, detail="Рекомендация не найдена.")
    return {"result_id": result_id, "rec_id": rec_id, "status": body.status}


# ---------------------------------------------------------------------------
# GET /api/v1/methodologies
# ---------------------------------------------------------------------------

@router.get("/methodologies", summary="Список реализованных методик RCA")
async def list_methodologies() -> dict:
    return {"supported": [m.value for m in _service.supported_methodologies()]}

@router.post(
    "/analyze-multi",
    response_model=list[RCAResult],
    status_code=status.HTTP_201_CREATED,
)
async def analyze_multi(
    request: MultiAnalysisRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> list[RCAResult]:
    results = await _service.analyze_multi(request)
    repo = RCARepository(db)
    for result in results:
        await repo.save_result(result, user_id=current_user.user_id)
        result.user_id = current_user.user_id
    return results


@router.get("/results/compare", response_model=ComparisonResult)
async def compare_results(
    incident_id: str = Query(..., description="ID инцидента"),
    db: DbSession,
    current_user: CurrentUser,
) -> ComparisonResult:
    repo = RCARepository(db)
    user_filter = None if current_user.role == "admin" else current_user.user_id
    results = await repo.list_results(user_id=user_filter, incident_id=incident_id, limit=10)
    if not results:
        raise HTTPException(status_code=404, detail="Нет результатов")
    for r in results:
        _check_owner_or_admin(r, current_user)
    return _service.compare(results)