"""
FastAPI-роутер: загрузка DOCX-отчёта и извлечение полей через LLM.

Эндпоинт принимает multipart/form-data с DOCX-файлом,
извлекает текст и отправляет в LLM для структурирования.

Кэш: повторная загрузка того же файла (по SHA-256) пропускает LLM и
возвращает результат из БД за миллисекунды.

Защита: auth-cookie (или Bearer) + CSRF.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.models import UserInfo
from src.auth.service import get_current_user
from src.db.base import get_db
from src.services.docx_extractor import extract_text_from_docx
from src.services.docx_fields_service import extract_fields_from_text
from src.services.docx_cache_service import get_or_extract
from src.domain.models import LLMResponseValidationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["upload"])

CurrentUser = Annotated[UserInfo, Depends(get_current_user)]
DBSession = Annotated[AsyncSession, Depends(get_db)]

# Лимит размера файла: 10 МБ
MAX_FILE_SIZE = 10 * 1024 * 1024


class VictimFields(BaseModel):
    """Сведения о пострадавшем, извлечённые из отчёта."""
    full_name: Optional[str] = None
    birth_date: Optional[str] = None
    age: Optional[int] = None
    family_status: Optional[str] = None
    children_under_21: Optional[int] = None
    profession: Optional[str] = None
    workplace: Optional[str] = None
    total_experience: Optional[str] = None
    experience_in_organization: Optional[str] = None
    qualification_certificate: Optional[str] = None
    introductory_briefing: Optional[str] = None
    workplace_briefing: Optional[str] = None
    internship: Optional[str] = None
    safety_knowledge_test: Optional[str] = None
    medical_examination: Optional[str] = None
    diagnosis_severity: Optional[str] = None


class ExtractedFields(BaseModel):
    """Результат извлечения полей из отчёта."""
    title: str
    description: str
    incident_date: Optional[str] = None
    incident_time: Optional[str] = None
    company: Optional[str] = None
    department: Optional[str] = None
    location: str
    incident_type: str
    severity: str

    victims: int = 0
    injured_count: Optional[int] = None
    fatalities_count: Optional[int] = None

    equipment: Optional[str] = None
    conditions: Optional[str] = None
    actions_taken: Optional[str] = None
    short_description: Optional[str] = None

    scene_description: Optional[str] = None
    equipment_description: Optional[str] = None
    full_circumstances: Optional[str] = None
    established_facts: Optional[str] = None

    victims_list: List[VictimFields] = Field(default_factory=list)


def _validate_docx_file(filename: str, file_bytes: bytes) -> None:
    """Бросает HTTPException при недопустимом файле."""
    if not filename.lower().endswith(".docx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Допустимы только файлы формата .docx",
        )
    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Файл пустой",
        )
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Файл слишком большой (макс. {MAX_FILE_SIZE // (1024 * 1024)} МБ)",
        )


def _normalize_victims(fields: dict) -> list:
    raw = fields.get("victims_list", [])
    result = []
    for v in raw:
        if isinstance(v, dict):
            try:
                result.append(VictimFields(**v))
            except Exception:
                result.append(VictimFields())
    return result


def _normalize_victims_as_dicts(fields: dict) -> list:
    raw = fields.get("victims_list", [])
    result = []
    for v in raw:
        if isinstance(v, dict):
            try:
                result.append(VictimFields(**v).model_dump())
            except Exception:
                pass
    return result


@router.post(
    "/upload-report",
    response_model=ExtractedFields,
    status_code=status.HTTP_200_OK,
    summary="Загрузить DOCX-отчёт и извлечь поля инцидента через LLM (с кэшем)",
)
async def upload_report(
    current_user: CurrentUser,
    db: DBSession,
    file: UploadFile = File(..., description="DOCX-файл отчёта об инциденте"),
) -> ExtractedFields:
    filename = file.filename or ""
    file_bytes = await file.read()
    _validate_docx_file(filename, file_bytes)

    logger.info(
        "[Upload] Пользователь %s загружает файл '%s' (%d байт)",
        current_user.user_id, filename, len(file_bytes),
    )

    try:
        fields = await get_or_extract(file_bytes, db)
    except LLMResponseValidationError as exc:
        logger.error("[Upload] LLM не вернул валидный ответ: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="ИИ не смог обработать отчёт. Попробуйте ещё раз.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    fields["victims_list"] = _normalize_victims(fields)
    return ExtractedFields(**fields)


@router.post(
    "/upload-report-stream",
    status_code=status.HTTP_200_OK,
    summary="Загрузить DOCX-отчёт и извлечь поля инцидента через LLM (SSE-поток, с кэшем)",
)
async def upload_report_stream(
    current_user: CurrentUser,
    db: DBSession,
    file: UploadFile = File(..., description="DOCX-файл отчёта об инциденте"),
):
    filename = file.filename or ""
    file_bytes = await file.read()

    try:
        _validate_docx_file(filename, file_bytes)
    except HTTPException as exc:
        async def _err():
            yield f"data: {json.dumps({'status': 'error', 'message': exc.detail})}\n\n"
        return StreamingResponse(_err(), media_type="text/event-stream")

    file_hash = hashlib.sha256(file_bytes).hexdigest()

    async def event_generator():
        from src.db.cache_repository import ExtractionCacheRepository
        repo = ExtractionCacheRepository(db)

        # --- Проверка кэша ---
        cached = await repo.get(file_hash)
        if cached is not None:
            logger.info("[UploadStream] Кэш-попадание: hash=%s", file_hash[:16])
            cached["victims_list"] = _normalize_victims_as_dicts(cached)
            yield f"data: {json.dumps({'status': 'cache_hit', 'message': 'Результат из кэша (повторный файл)'})}\n\n"
            await asyncio.sleep(0.05)
            yield f"data: {json.dumps({'status': 'done', 'result': cached})}\n\n"
            return

        # --- Кэш-промах: полный pipeline ---
        yield f"data: {json.dumps({'status': 'reading', 'message': 'Извлечение текста из документа...'})}\n\n"
        await asyncio.sleep(0.05)

        try:
            report_text = extract_text_from_docx(file_bytes)
        except Exception as exc:
            logger.error("[UploadStream] Ошибка парсинга DOCX: %s", exc)
            yield f"data: {json.dumps({'status': 'error', 'message': 'Не удалось прочитать DOCX-файл. Убедитесь, что файл не повреждён.'})}\n\n"
            return

        if not report_text.strip():
            yield f"data: {json.dumps({'status': 'error', 'message': 'Документ не содержит текста'})}\n\n"
            return

        yield f"data: {json.dumps({'status': 'analyzing', 'message': 'Анализ текста в LLM (это может занять до 6-7 минут)...'})}\n\n"

        try:
            fields = await extract_fields_from_text(report_text)
        except LLMResponseValidationError as exc:
            logger.error("[UploadStream] LLM не вернул валидный ответ: %s", exc)
            yield f"data: {json.dumps({'status': 'error', 'message': 'ИИ не смог обработать отчёт. Попробуйте ещё раз.'})}\n\n"
            return
        except ValueError as exc:
            yield f"data: {json.dumps({'status': 'error', 'message': str(exc)})}\n\n"
            return
        except Exception as exc:
            logger.error("[UploadStream] Неизвестная ошибка: %s", exc)
            yield f"data: {json.dumps({'status': 'error', 'message': 'Произошла непредвиденная ошибка при анализе отчёта.'})}\n\n"
            return

        # Сохраняем в кэш (raw dict, без нормализованных жертв)
        await repo.save(file_hash, fields)

        fields["victims_list"] = _normalize_victims_as_dicts(fields)
        yield f"data: {json.dumps({'status': 'done', 'result': fields})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
