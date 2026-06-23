"""Repository for admin-managed LLM conductor settings (P17)."""

from __future__ import annotations

import inspect
import os
from datetime import UTC, datetime
from typing import Any, Literal, cast

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.orm_models import LLMSettingsORM
from src.domain.models import LLMSettings, LLMSettingsUpdate

LLM_SETTINGS_SINGLETON_ID = 1
DEFAULT_DRAFT_MODEL = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-super-120b-a12b:free")
DEFAULT_VERIFIER_MODEL = os.getenv("OPENROUTER_VERIFIER_MODEL", "openai/gpt-oss-20b")
DEFAULT_QUALITY_THRESHOLD = 0.70
DEFAULT_VERIFICATION_SCHEME = "threshold"


async def _maybe_await(value: Any) -> None:
    """Support real AsyncSession and AsyncMock-based tests."""
    if inspect.isawaitable(value):
        await value


def _orm_to_domain(row: LLMSettingsORM) -> LLMSettings:
    return LLMSettings(
        draft_model=row.draft_model,
        verifier_model=row.verifier_model,
        quality_threshold=row.quality_threshold,
        verification_scheme=cast('Literal["disabled", "threshold", "always"]', row.verification_scheme),
        updated_at=row.updated_at,
        updated_by=row.updated_by,
    )


class LLMSettingsRepository:
    """Read/update singleton LLM settings used by the future LLMConductor."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self) -> LLMSettings:
        """
        Return settings, creating the singleton row if it is missing.

        The migration seeds id=1, but get-or-create keeps local/dev/test DBs robust.
        """
        row = await self._session.get(LLMSettingsORM, LLM_SETTINGS_SINGLETON_ID)
        if row is None:
            row = LLMSettingsORM(
                id=LLM_SETTINGS_SINGLETON_ID,
                draft_model=DEFAULT_DRAFT_MODEL,
                verifier_model=DEFAULT_VERIFIER_MODEL,
                quality_threshold=DEFAULT_QUALITY_THRESHOLD,
                verification_scheme=DEFAULT_VERIFICATION_SCHEME,
                updated_at=datetime.now(UTC),
                updated_by=None,
            )
            await _maybe_await(self._session.add(row))  # type: ignore[func-returns-value]
            await self._session.commit()
            await self._session.refresh(row)
        return _orm_to_domain(row)

    async def upsert(self, body: LLMSettingsUpdate, *, updated_by: str | None) -> LLMSettings:
        """Create or update the singleton settings row."""
        row = await self._session.get(LLMSettingsORM, LLM_SETTINGS_SINGLETON_ID)
        now = datetime.now(UTC)

        if row is None:
            row = LLMSettingsORM(
                id=LLM_SETTINGS_SINGLETON_ID,
                draft_model=body.draft_model,
                verifier_model=body.verifier_model,
                quality_threshold=body.quality_threshold,
                verification_scheme=body.verification_scheme,
                updated_at=now,
                updated_by=updated_by,
            )
            await _maybe_await(self._session.add(row))  # type: ignore[func-returns-value]
        else:
            row.draft_model = body.draft_model
            row.verifier_model = body.verifier_model
            row.quality_threshold = body.quality_threshold
            row.verification_scheme = body.verification_scheme
            row.updated_at = now
            row.updated_by = updated_by

        await self._session.commit()
        await self._session.refresh(row)
        return _orm_to_domain(row)
