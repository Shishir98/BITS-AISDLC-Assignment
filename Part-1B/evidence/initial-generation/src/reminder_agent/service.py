from __future__ import annotations

import json
from datetime import datetime
from typing import Protocol
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from reminder_agent.config import Settings
from reminder_agent.errors import InvalidModelOutputError
from reminder_agent.prompts import build_messages, load_prompt_bundle
from reminder_agent.schemas import InterpretationRequest, InterpretationResult
from reminder_agent.temporal import (
    analyze_temporal_text,
    has_explicit_target,
    has_reminder_description,
    has_snooze_duration,
    validate_scheduled_datetime,
)


class InferenceClient(Protocol):
    async def generate(self, system: str, user: str, schema: dict) -> str: ...


class InterpretationService:
    def __init__(self, client: InferenceClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings
        self.prompt_bundle = load_prompt_bundle()

    async def interpret(self, request: InterpretationRequest) -> InterpretationResult:
        messages = build_messages(
            self.prompt_bundle,
            request.text,
            request.reference_datetime.isoformat(),
            request.timezone,
        )
        raw_output = await self.client.generate(
            messages[0]["content"],
            messages[1]["content"],
            self.prompt_bundle.schema,
        )
        return self.interpret_response(request, raw_output)

    def interpret_response(
        self, request: InterpretationRequest, raw_output: str
    ) -> InterpretationResult:
        try:
            payload = json.loads(raw_output)
            result = InterpretationResult.model_validate(payload)
        except (json.JSONDecodeError, TypeError, ValidationError) as exc:
            raise InvalidModelOutputError(raw_output=raw_output) from exc

        if result.timezone != request.timezone:
            raise InvalidModelOutputError(raw_output=raw_output)
        if result.status != "ready":
            return result
        if result.intent == "snooze":
            if not has_explicit_target(request.text):
                return self._clarification(
                    result,
                    "Which reminder should I snooze?",
                    target_reference=None,
                )
            if not has_snooze_duration(request.text):
                return self._clarification(
                    result,
                    "For how many minutes should I snooze it?",
                    snooze_minutes=None,
                )
            return result
        if result.intent not in {"create", "reschedule"}:
            return result
        if result.scheduled_at is None:
            raise InvalidModelOutputError(raw_output=raw_output)
        if result.intent == "create" and not has_reminder_description(request.text):
            return self._clarification(
                result, "What should I remind you about?", title=None
            )
        if result.intent == "reschedule" and not has_explicit_target(request.text):
            return self._clarification(
                result, "Which reminder should I move?", target_reference=None
            )

        hint = analyze_temporal_text(
            request.text, request.reference_datetime, request.timezone
        )
        if hint.issue is not None:
            return self._clarification(result, _question_for_issue(hint.issue))
        if not hint.date_known or not hint.time_known or hint.local_datetime is None:
            return self._clarification(result, _question_for_missing(hint))

        scheduled_at = result.scheduled_at
        if not validate_scheduled_datetime(
            scheduled_at, request.reference_datetime, request.timezone
        ):
            if scheduled_at.astimezone(ZoneInfo(request.timezone)).utcoffset() != scheduled_at.utcoffset():
                raise InvalidModelOutputError(raw_output=raw_output)
            return self._clarification(
                result, "That time is not in the future. What future date and time should I use?"
            )
        if scheduled_at.astimezone(ZoneInfo(request.timezone)).replace(
            tzinfo=None
        ) != hint.local_datetime:
            raise InvalidModelOutputError(raw_output=raw_output)
        return result

    @staticmethod
    def _clarification(
        result: InterpretationResult, question: str, **overrides: str | None
    ) -> InterpretationResult:
        payload = result.model_dump()
        payload.update(
            status="clarification_required",
            scheduled_at=None,
            clarification_questions=[question],
            user_message=question,
        )
        payload.update(overrides)
        return InterpretationResult.model_validate(payload)


def _question_for_issue(issue: str) -> str:
    if issue == "nonexistent":
        return "That local time does not exist because of a clock change. What other time should I use?"
    if issue == "ambiguous":
        return "That local time occurs twice because of a clock change. Which occurrence do you mean?"
    if issue in {"invalid_date", "past_date_without_year", "past_weekday"}:
        return "That date is invalid or has passed. What future date should I use?"
    return "Please provide an unambiguous future date and time."


def _question_for_missing(hint: object) -> str:
    missing: list[str] = []
    if not getattr(hint, "date_known"):
        missing.append("date")
    if not getattr(hint, "time_known"):
        missing.append("exact time")
    if missing == ["date", "exact time"]:
        return "What date and exact time should I use?"
    if missing:
        return f"What {' and '.join(missing)} should I use?"
    return "Please provide an unambiguous future date and time."
