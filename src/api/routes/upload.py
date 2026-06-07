"""
FastAPI-роутер: загрузка DOCX-отчёта и извлечение полей через LLM.

Эндпоинт принимает multipart/form-data с DOCX-файлом,
извлекает текст и отправляет в LLM для структурирования.

Защита: auth-cookie (или Bearer) + CSRF.
"""

from __future__ import annotations

import logging
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import json
import asyncio

from src.auth.models import UserInfo
from src.auth.service import get_current_user
from src.services.docx_extractor import extract_text_from_docx
from src.services.docx_fields_service import extract_fields_from_text
from src.domain.models import LLMResponseValidationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["upload"])

CurrentUser = Annotated[UserInfo, Depends(get_current_user)]

# Лимит размера файла: 10 МБ
MAX_FILE_SIZE = 10 * 1024 * 1024

# Допустимые MIME-типы для DOCX
ALLOWED_CONTENT_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/octet-stream",  # Некоторые браузеры отправляют этот тип
}


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
    # Основные поля
    title: str
    description: str
    incident_date: Optional[str] = None
    incident_time: Optional[str] = None
    company: Optional[str] = None
    department: Optional[str] = None
    location: str
    incident_type: str
    severity: str

    # Числовые счётчики
    victims: int = 0
    injured_count: Optional[int] = None
    fatalities_count: Optional[int] = None

    # Дополнительные текстовые поля (старые)
    equipment: Optional[str] = None
    conditions: Optional[str] = None
    actions_taken: Optional[str] = None
    short_description: Optional[str] = None

    # Расширенные поля (разделы 3.x)
    scene_description: Optional[str] = None
    equipment_description: Optional[str] = None
    full_circumstances: Optional[str] = None
    established_facts: Optional[str] = None

    # Список пострадавших
    victims_list: List[VictimFields] = Field(default_factory=list)


@router.post(
    "/upload-report",
    response_model=ExtractedFields,
    status_code=status.HTTP_200_OK,
    summary="Загрузить DOCX-отчёт и извлечь поля инцидента через LLM",
)
async def upload_report(
    current_user: CurrentUser,
    file: UploadFile = File(..., description="DOCX-файл отчёта об инциденте"),
) -> ExtractedFields:
    # --- Валидация файла ---
    filename = file.filename or ""
    if not filename.lower().endswith(".docx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Допустимы только файлы формата .docx",
        )

    # Читаем содержимое
    file_bytes = await file.read()

    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Файл пустой",
        )

    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Файл слишком большой (макс. {MAX_FILE_SIZE // (1024*1024)} МБ)",
        )

    logger.info(
        "[Upload] Пользователь %s загружает файл '%s' (%d байт)",
        current_user.user_id,
        filename,
        len(file_bytes),
    )

    # --- Извлечение текста из DOCX ---
    try:
        report_text = extract_text_from_docx(file_bytes)
    except Exception as exc:
        logger.error("[Upload] Ошибка парсинга DOCX: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не удалось прочитать DOCX-файл. Убедитесь, что файл не повреждён.",
        ) from exc

    if not report_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Документ не содержит текста",
        )

    # --- Извлечение полей через LLM ---
    try:
        fields = await extract_fields_from_text(report_text)
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

    # Нормализуем victims_list в объекты VictimFields
    raw_victims = fields.get("victims_list", [])
    victims_parsed = []
    for v in raw_victims:
        if isinstance(v, dict):
            try:
                victims_parsed.append(VictimFields(**v))
            except Exception:
                victims_parsed.append(VictimFields())
    fields["victims_list"] = victims_parsed

    return ExtractedFields(**fields)

@router.post(
    "/upload-report-stream",
    status_code=status.HTTP_200_OK,
    summary="Загрузить DOCX-отчёт и извлечь поля инцидента через LLM (SSE-поток)",
)
async def upload_report_stream(
    current_user: CurrentUser,
    file: UploadFile = File(..., description="DOCX-файл отчёта об инциденте"),
):
    # --- Валидация файла ---
    filename = file.filename or ""
    if not filename.lower().endswith(".docx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Допустимы только файлы формата .docx",
        )

    file_bytes = await file.read()

    if len(file_bytes) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Файл пустой")

    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Файл слишком большой (макс. {MAX_FILE_SIZE // (1024*1024)} МБ)",
        )

    async def event_generator():
        # Стадия 1: Чтение документа
        yield f"data: {json.dumps({'status': 'reading', 'message': 'Извлечение текста из документа...'})}\n\n"
        await asyncio.sleep(0.1) # Даем событию отправиться
        
        try:
            report_text = extract_text_from_docx(file_bytes)
        except Exception as exc:
            logger.error("[UploadStream] Ошибка парсинга DOCX: %s", exc)
            yield f"data: {json.dumps({'status': 'error', 'message': 'Не удалось прочитать DOCX-файл. Убедитесь, что файл не повреждён.'})}\n\n"
            return

        if not report_text.strip():
            yield f"data: {json.dumps({'status': 'error', 'message': 'Документ не содержит текста'})}\n\n"
            return

        # Стадия 2: LLM
        yield f"data: {json.dumps({'status': 'analyzing', 'message': 'Анализ текста в LLM (это может занять до 1-2 минут)...'})}\n\n"
        
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

        # Нормализуем victims_list
        raw_victims = fields.get("victims_list", [])
        victims_parsed = []
        for v in raw_victims:
            if isinstance(v, dict):
                try:
                    victims_parsed.append(VictimFields(**v).model_dump())
                except Exception:
                    pass
        fields["victims_list"] = victims_parsed

        # Стадия 3: Готово
        yield f"data: {json.dumps({'status': 'done', 'result': fields})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
