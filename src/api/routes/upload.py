"""
FastAPI-роутер: загрузка DOCX-отчёта и извлечение полей через LLM.

Эндпоинт принимает multipart/form-data с DOCX-файлом,
извлекает текст и отправляет в LLM для структурирования.

Кэш: повторная загрузка того же файла (по SHA-256) пропускает LLM и
возвращает результат из БД за миллисекунды — НО только если предыдущее
извлечение было полным (full_circumstances + established_facts непустые).
Если группа narrative упала — кэш не пишется, следующий запрос идёт в LLM.

Защита: auth-cookie (или Bearer) + CSRF.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.models import UserInfo
from src.auth.service import get_current_user
from src.db.base import get_db
from src.db.cache_repository import ExtractionCacheRepository
from src.db.repository import compute_incident_hash
from src.domain.models import LLMResponseValidationError
from src.services.docx_cache_service import _is_complete, get_or_extract
from src.services.docx_extractor import extract_text_from_docx
from src.services.docx_fields_service import extract_fields_from_text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["upload"])

CurrentUser = Annotated[UserInfo, Depends(get_current_user)]
DBSession = Annotated[AsyncSession, Depends(get_db)]

MAX_FILE_SIZE = 20 * 1024 * 1024


async def _read_limited(file: UploadFile, max_size: int) -> bytes:
    """Читать файл чанками по 1МБ с проверкой лимита до полной загрузки."""
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(1024 * 1024):
        total += len(chunk)
        if total > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Файл слишком большой (макс. {max_size // (1024 * 1024)} МБ)",
            )
        chunks.append(chunk)
    return b"".join(chunks)

_NARRATIVE_REQUIRED = ("full_circumstances", "established_facts")


class VictimFields(BaseModel):
    full_name: str | None = None
    birth_date: str | None = None
    age: int | None = None
    family_status: str | None = None
    children_under_21: int | None = None
    profession: str | None = None
    workplace: str | None = None
    total_experience: str | None = None
    experience_in_organization: str | None = None
    qualification_certificate: str | None = None
    introductory_briefing: str | None = None
    workplace_briefing: str | None = None
    internship: str | None = None
    safety_knowledge_test: str | None = None
    medical_examination: str | None = None
    diagnosis_severity: str | None = None


class ExtractedFields(BaseModel):
    title: str
    description: str
    incident_date: str | None = None
    incident_time: str | None = None
    company: str | None = None
    department: str | None = None
    location: str
    incident_type: str
    severity: str
    victims: int = 0
    injured_count: int | None = None
    fatalities_count: int | None = None
    equipment: str | None = None
    conditions: str | None = None
    actions_taken: str | None = None
    short_description: str | None = None
    scene_description: str | None = None
    equipment_description: str | None = None
    full_circumstances: str | None = None
    established_facts: str | None = None
    victims_list: list[VictimFields] = Field(default_factory=list)


def _validate_docx_file(filename: str, file_bytes: bytes) -> None:
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
    file_bytes = await _read_limited(file, MAX_FILE_SIZE)
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
    file_bytes = await _read_limited(file, MAX_FILE_SIZE)

    try:
        _validate_docx_file(filename, file_bytes)
    except HTTPException as exc:
        async def _err(err_exc):
            yield f"data: {json.dumps({'status': 'error', 'message': err_exc.detail})}\n\n"
        return StreamingResponse(_err(exc), media_type="text/event-stream")

    file_hash = hashlib.sha256(file_bytes).hexdigest()

    async def event_generator():
        from src.db.cache_repository import ExtractionCacheRepository
        repo = ExtractionCacheRepository(db)

        cached = await repo.get(file_hash)
        if cached is not None:
            logger.info("[UploadStream] Кэш-попадание: hash=%s", file_hash[:16])
            cached["victims_list"] = _normalize_victims_as_dicts(cached)
            yield f"data: {json.dumps({'status': 'cache_hit', 'message': 'Результат из кэша (повторный файл)'})}\n\n"
            await asyncio.sleep(0.05)
            yield f"data: {json.dumps({'status': 'done', 'result': cached})}\n\n"
            return

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

        if _is_complete(fields):
            # Дедупликация по incident_hash (тот же инцидент, другой файл)
            title = fields.get("title", "")
            description = fields.get("description", "")
            if title and description:
                inc_hash = compute_incident_hash(title, description)
                dup = await repo.find_by_incident_hash(inc_hash)
                if dup is not None:
                    logger.info(
                        "[UploadStream] Дедупликация: найден по incident_hash=%s — "
                        "возвращаю существующие данные",
                        inc_hash[:16],
                    )
                    dup["_metadata"] = {"dedup_from": inc_hash[:16]}
                    await repo._hard_save(file_hash, inc_hash, dup)
                    dup["victims_list"] = _normalize_victims_as_dicts(dup)
                    yield f"data: {json.dumps({'status': 'cache_hit', 'message': 'Найден дубликат инцидента (тот же title+description)'})}\\n\\n"
                    await asyncio.sleep(0.05)
                    yield f"data: {json.dumps({'status': 'done', 'result': dup})}\\n\\n"
                    return
                await repo._hard_save(file_hash, inc_hash, fields)
            else:
                await repo.save(file_hash, fields)
        else:
            missing = [k for k in _NARRATIVE_REQUIRED if not fields.get(k)]
            missing_str = ", ".join(missing)
            logger.warning(
                "[UploadStream] Результат неполный (пустые: %s) — кэш не сохранён",
                missing_str,
            )
            warn_msg = "Некоторые поля не извлечены (" + missing_str + "). Попробуйте загрузить файл ещё раз."
            yield f"data: {json.dumps({'status': 'warning', 'message': warn_msg})}\n\n"
            await asyncio.sleep(0.05)

        fields["victims_list"] = _normalize_victims_as_dicts(fields)
        yield f"data: {json.dumps({'status': 'done', 'result': fields})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
