from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

_RFC3339_DATETIME = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)


class InterpretationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    text: str = Field(min_length=1)
    reference_datetime: AwareDatetime
    timezone: str = Field(min_length=1)

    @field_validator("reference_datetime", mode="before")
    @classmethod
    def require_offset_datetime(cls, value: object) -> object:
        if isinstance(value, str) and not _RFC3339_DATETIME.fullmatch(value):
            raise ValueError("reference_datetime must be RFC 3339 with an offset")
        if isinstance(value, datetime) and (
            value.tzinfo is None or value.utcoffset() is None
        ):
            raise ValueError("reference_datetime must be timezone-aware")
        return value

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ValueError, ZoneInfoNotFoundError) as exc:
            raise ValueError("timezone must be a valid IANA identifier") from exc
        return value


class InterpretationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: Literal["ready", "clarification_required", "unsupported"]
    intent: Literal["create", "reschedule", "snooze", "unknown"]
    title: str | None
    scheduled_at: AwareDatetime | None
    timezone: str = Field(min_length=1)
    target_reference: str | None
    snooze_minutes: int | None = Field(strict=True)
    clarification_questions: list[str]
    user_message: str = Field(min_length=1, max_length=240)

    @field_validator("scheduled_at", mode="before")
    @classmethod
    def require_offset_datetime(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str) and not _RFC3339_DATETIME.fullmatch(value):
            raise ValueError("scheduled_at must be RFC 3339 with an offset")
        if isinstance(value, datetime) and (
            value.tzinfo is None or value.utcoffset() is None
        ):
            raise ValueError("scheduled_at must be timezone-aware")
        return value

    @field_validator("title", "target_reference")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("text values must be non-empty when present")
        return value

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ValueError, ZoneInfoNotFoundError) as exc:
            raise ValueError("timezone must be a valid IANA identifier") from exc
        return value

    @field_validator("snooze_minutes")
    @classmethod
    def validate_snooze_minutes(cls, value: int | None) -> int | None:
        if value is not None and (isinstance(value, bool) or value <= 0):
            raise ValueError("snooze_minutes must be a positive integer")
        return value

    @field_validator("clarification_questions")
    @classmethod
    def validate_questions(cls, value: list[str]) -> list[str]:
        if any(not question.strip() or len(question) > 240 for question in value):
            raise ValueError("clarification questions must be concise non-empty strings")
        return value

    @model_validator(mode="after")
    def validate_relationships(self) -> InterpretationResult:
        if self.status == "ready":
            if self.clarification_questions:
                raise ValueError("ready results cannot contain clarification questions")
            if self.intent == "create":
                if (
                    not self.title
                    or self.scheduled_at is None
                    or self.target_reference is not None
                    or self.snooze_minutes is not None
                ):
                    raise ValueError("ready CREATE requires only title and scheduled_at")
            elif self.intent == "reschedule":
                if (
                    self.title is not None
                    or self.scheduled_at is None
                    or not self.target_reference
                    or self.snooze_minutes is not None
                ):
                    raise ValueError(
                        "ready RESCHEDULE requires target_reference and scheduled_at"
                    )
            elif self.intent == "snooze":
                if (
                    self.title is not None
                    or self.scheduled_at is not None
                    or not self.target_reference
                    or self.snooze_minutes is None
                ):
                    raise ValueError(
                        "ready SNOOZE requires target_reference and snooze_minutes"
                    )
            else:
                raise ValueError("ready results require a supported intent")
        elif self.status == "clarification_required":
            if self.scheduled_at is not None or not self.clarification_questions:
                raise ValueError(
                    "clarification requires questions and a null scheduled_at"
                )
        else:
            if (
                self.intent != "unknown"
                or self.title is not None
                or self.scheduled_at is not None
                or self.target_reference is not None
                or self.snooze_minutes is not None
                or self.clarification_questions
            ):
                raise ValueError(
                    "unsupported results must be unknown and contain no action fields"
                )
        return self


def load_openapi_contract() -> dict:
    project_root = Path(__file__).resolve().parents[2]
    contract_path = (
        project_root
        / "specs"
        / "001-natural-language-reminder-agent"
        / "contracts"
        / "interpretation.openapi.yaml"
    )
    return yaml.safe_load(contract_path.read_text(encoding="utf-8"))


def load_response_schema() -> dict:
    contract = load_openapi_contract()
    return contract["components"]["schemas"]["InterpretationResult"]
