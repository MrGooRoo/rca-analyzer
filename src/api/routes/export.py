"""
Export роутер.

GET /api/v1/results/{result_id}/export
  → возвращает DOCX-файл как вложение.

Требует auth-cookie или Bearer-токен.
Возвращает 403, если result принадлежит другому пользователю.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.models import UserInfo
from src.auth.service import get_current_user
from src.db.base import get_db
from src.db.repository import RCARepository
from src.services.export_service import generate_docx

router = APIRouter(prefix="/api/v1", tags=["export"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[UserInfo, Depends(get_current_user)]


@router.get(
    "/results/{result_id}/export",
    summary="Экспорт результата RCA в DOCX",
    response_class=Response,
    responses={
        200: {
            "content": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document": {}},
            "description": "DOCX-файл с отчётом RCA",
        },
        403: {"description": "Результат принадлежит другому пользователю"},
        404: {"description": "Результат не найден"},
    },
)
async def export_result(
    result_id: str,
    db: DbSession,
    current_user: CurrentUser,
) -> Response:
    repo = RCARepository(db)
    result = await repo.get_result(result_id)

    if result is None:
        raise HTTPException(status_code=404, detail=f"Результат '{result_id}' не найден.")
    if result.user_id and result.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    docx_bytes = generate_docx(result)

    filename = f"rca_{result.methodology.value}_{result.result_id[:8]}.docx"
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
