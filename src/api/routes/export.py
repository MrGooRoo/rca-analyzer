"""
Export роутер.

GET /api/v1/results/{result_id}/export?format=docx|pdf
  → возвращает DOCX- или PDF-файл как вложение (по умолчанию DOCX).

Требует auth-cookie или Bearer-токен.
Возвращает 403, если result принадлежит другому пользователю (и он не admin).
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.models import UserInfo
from src.auth.service import get_current_user
from src.db.base import get_db
from src.db.repository import RCARepository
from src.services.export_service import generate_docx
from src.services.pdf_export_service import generate_pdf

_DOCX_MEDIA = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_PDF_MEDIA = "application/pdf"

router = APIRouter(prefix="/api/v1", tags=["export"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[UserInfo, Depends(get_current_user)]


def _check_owner_or_admin(result, current_user: UserInfo) -> None:
    """Проверить, что пользователь — владелец записи или admin."""
    if current_user.role == "admin":
        return
    if result.user_id and result.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Доступ запрещён")


@router.get(
    "/results/{result_id}/export",
    summary="Экспорт результата RCA в DOCX или PDF",
    response_class=Response,
    responses={
        200: {
            "content": {_DOCX_MEDIA: {}, _PDF_MEDIA: {}},
            "description": "DOCX- или PDF-файл с отчётом RCA",
        },
        403: {"description": "Результат принадлежит другому пользователю"},
        404: {"description": "Результат не найден"},
    },
)
async def export_result(
    result_id: str,
    db: DbSession,
    current_user: CurrentUser,
    fmt: Annotated[
        Literal["docx", "pdf"],
        Query(alias="format", description="Формат экспорта: docx (по умолчанию) или pdf"),
    ] = "docx",
) -> Response:
    repo = RCARepository(db)
    result = await repo.get_result(result_id)

    if result is None:
        raise HTTPException(status_code=404, detail=f"Результат '{result_id}' не найден.")
    _check_owner_or_admin(result, current_user)

    if fmt == "pdf":
        content = generate_pdf(result)
        media_type = _PDF_MEDIA
        ext = "pdf"
    else:
        content = generate_docx(result)
        media_type = _DOCX_MEDIA
        ext = "docx"

    filename = f"rca_{result.methodology.value}_{result.result_id[:8]}.{ext}"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
