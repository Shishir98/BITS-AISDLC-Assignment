from __future__ import annotations

import json
import re
from typing import Protocol
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from reminder_agent.config import Settings
from reminder_agent.errors import InvalidModelOutputError
from reminder_agent.prompts import build_messages, load_prompt_bundle
from reminder_agent.safety import claims_external_action, contains_private_reasoning
from reminder_agent.schemas import InterpretationRequest, InterpretationResult
from reminder_agent.temporal import (
    TemporalHint,
    analyze_temporal_text,
    extract_snooze_minutes,
    has_explicit_target,
    has_reminder_description,
    has_supported_reminder_operation,
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

        if _contains_private_reasoning(result):
            raise InvalidModelOutputError(raw_output=raw_output)
        if not _no_external_action_claim(result.user_message):
            raise InvalidModelOutputError(raw_output=raw_output)
        if result.timezone != request.timezone:
            raise InvalidModelOutputError(raw_output=raw_output)
        if not has_supported_reminder_operation(request.text):
            return self._unsupported(request.timezone)
        if result.status == "unsupported" or result.intent == "unknown":
            if any(
                value is not None and not _text_is_grounded(value, request.text)
                for value in (result.title, result.target_reference)
            ):
                raise InvalidModelOutputError(raw_output=raw_output)
            return result
        if result.intent == "snooze":
            target_present = has_explicit_target(request.text)
            requested_duration = extract_snooze_minutes(request.text)
            if not target_present:
                return self._clarification(
                    result,
                    "Which reminder should I snooze?",
                    target_reference=None,
                )
            if result.target_reference is not None and not _text_is_grounded(
                result.target_reference, request.text
            ):
                raise InvalidModelOutputError(raw_output=raw_output)
            if requested_duration is None:
                return self._clarification(
                    result,
                    "For how many minutes should I snooze it?",
                    snooze_minutes=None,
                )
            if requested_duration <= 0:
                return self._clarification(
                    result,
                    "Please provide a positive snooze duration in minutes.",
                    snooze_minutes=None,
                )
            if result.status == "ready" and requested_duration != result.snooze_minutes:
                raise InvalidModelOutputError(raw_output=raw_output)
            if result.status == "clarification_required":
                return result
            return result

        if result.intent == "create":
            if not has_reminder_description(request.text):
                return self._clarification(
                    result, "What should I remind you about?", title=None
                )
            if result.title is not None and not _text_is_grounded(result.title, request.text):
                raise InvalidModelOutputError(raw_output=raw_output)
            if result.status == "clarification_required":
                return self._temporal_clarification(result, request) or result
            if result.title is None:
                return self._clarification(
                    result, "What should I remind you about?", title=None
                )
        elif result.intent == "reschedule":
            if not has_explicit_target(request.text):
                return self._clarification(
                    result, "Which reminder should I move?", target_reference=None
                )
            if result.target_reference is not None and not _text_is_grounded(
                result.target_reference, request.text
            ):
                raise InvalidModelOutputError(raw_output=raw_output)
            if result.status == "clarification_required":
                return self._temporal_clarification(result, request) or result
            if result.target_reference is None:
                return self._clarification(
                    result, "Which reminder should I move?", target_reference=None
                )

        return self._validate_schedule(result, request, raw_output)

    def _temporal_clarification(
        self, result: InterpretationResult, request: InterpretationRequest
    ) -> InterpretationResult | None:
        hint = analyze_temporal_text(
            request.text, request.reference_datetime, request.timezone
        )
        if hint.issue is not None:
            return self._clarification(result, _question_for_issue(hint.issue))
        if not hint.date_known or not hint.time_known or hint.local_datetime is None:
            return self._clarification(result, _question_for_missing(hint))
        return None

    def _validate_schedule(
        self,
        result: InterpretationResult,
        request: InterpretationRequest,
        raw_output: str,
    ) -> InterpretationResult:
        if result.scheduled_at is None:
            raise InvalidModelOutputError(raw_output=raw_output)
        clarification = self._temporal_clarification(result, request)
        if clarification is not None:
            return clarification
        hint = analyze_temporal_text(
            request.text, request.reference_datetime, request.timezone
        )
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
        if hint.fold is not None and scheduled_at.astimezone(
            ZoneInfo(request.timezone)
        ).fold != hint.fold:
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

    @staticmethod
    def _unsupported(timezone: str) -> InterpretationResult:
        return InterpretationResult.model_validate(
            {
                "status": "unsupported",
                "intent": "unknown",
                "title": None,
                "scheduled_at": None,
                "timezone": timezone,
                "target_reference": None,
                "snooze_minutes": None,
                "clarification_questions": [],
                "user_message": (
                    "I can only help create, reschedule, or snooze reminders."
                ),
            }
        )


def _question_for_issue(issue: str) -> str:
    if issue == "nonexistent":
        return "That local time does not exist because of a clock change. What other time should I use?"
    if issue == "ambiguous":
        return "That local time occurs twice because of a clock change. Which occurrence do you mean?"
    if issue in {"invalid_date", "past_date_without_year", "past_weekday"}:
        return "That date is invalid or has passed. What future date should I use?"
    return "Please provide an unambiguous future date and time."


def _question_for_missing(hint: TemporalHint) -> str:
    missing: list[str] = []
    if not hint.date_known:
        missing.append("date")
    if not hint.time_known:
        missing.append("exact time")
    if missing == ["date", "exact time"]:
        return "What date and exact time should I use?"
    if missing:
        return f"What {' and '.join(missing)} should I use?"
    return "Please provide an unambiguous future date and time."


def _contains_private_reasoning(result: InterpretationResult) -> bool:
    text_fields = [
        result.title or "",
        result.target_reference or "",
        result.user_message,
        *result.clarification_questions,
    ]
    return contains_private_reasoning(" ".join(text_fields))


def _no_external_action_claim(message: str) -> bool:
    return not claims_external_action(message)


def _text_is_grounded(value: str, user_text: str) -> bool:
    synonyms = {"phone": "call", "ring": "call"}
    ignored = {"a", "an", "the", "my", "me", "to", "reminder"}

    def tokens(text: str) -> list[str]:
        return [
            synonyms.get(word, word)
            for word in re.findall(r"\w+", text.casefold())
            if word not in ignored
        ]

    value_tokens = tokens(value)
    source_tokens = tokens(user_text)
    return bool(value_tokens) and any(
        source_tokens[index:index + len(value_tokens)] == value_tokens
        for index in range(len(source_tokens) - len(value_tokens) + 1)
    )
