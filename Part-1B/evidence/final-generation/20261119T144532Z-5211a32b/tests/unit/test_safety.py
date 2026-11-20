import asyncio
import json
from datetime import datetime

import pytest

from reminder_agent.config import Settings
from reminder_agent.errors import InvalidModelOutputError
from reminder_agent.schemas import InterpretationRequest
from reminder_agent.service import InterpretationService


class FakeClient:
    def __init__(self, content: str) -> None:
        self.content = content

    async def generate(self, _system: str, _user: str, _schema: dict) -> str:
        return self.content


def create_candidate(scheduled_at: str) -> dict:
    return {
        "status": "ready",
        "intent": "create",
        "title": "Call Rahul",
        "scheduled_at": scheduled_at,
        "timezone": "America/New_York",
        "target_reference": None,
        "snooze_minutes": None,
        "clarification_questions": [],
        "user_message": "I can propose a reminder to call Rahul.",
    }


def make_request(text: str) -> InterpretationRequest:
    return InterpretationRequest(
        text=text,
        reference_datetime=datetime.fromisoformat("2026-03-01T09:00:00-05:00"),
        timezone="America/New_York",
    )


def test_past_time_is_clarified_instead_of_shifted_or_returned_ready() -> None:
    client = FakeClient(json.dumps(create_candidate("2026-03-01T08:00:00-05:00")))
    service = InterpretationService(client, Settings.from_env({}))

    result = asyncio.run(
        service.interpret(make_request("Remind me to call Rahul today at 8 AM."))
    )

    assert result.status == "clarification_required"
    assert result.scheduled_at is None


def test_nonexistent_dst_time_is_always_clarified() -> None:
    candidate = create_candidate("2026-03-08T03:30:00-04:00")
    client = FakeClient(json.dumps(candidate))
    service = InterpretationService(client, Settings.from_env({}))
    request = InterpretationRequest(
        text="Remind me to call Rahul on March 8, 2026 at 2:30 AM.",
        reference_datetime=datetime.fromisoformat("2026-03-01T09:00:00-05:00"),
        timezone="America/New_York",
    )

    result = asyncio.run(service.interpret(request))

    assert result.status == "clarification_required"
    assert result.scheduled_at is None
    assert "does not exist" in result.user_message


@pytest.mark.parametrize(
    ("offset", "accepted"),
    [("-05:00", True), ("-04:00", False)],
)
def test_explicit_second_dst_occurrence_rejects_the_wrong_fold(
    offset: str, accepted: bool
) -> None:
    candidate = create_candidate(f"2026-11-01T01:30:00{offset}")
    request = InterpretationRequest(
        text="Remind me to call Rahul on November 1, 2026 at 1:30 AM, second occurrence.",
        reference_datetime=datetime.fromisoformat("2026-10-25T09:00:00-04:00"),
        timezone="America/New_York",
    )
    service = InterpretationService(FakeClient(json.dumps(candidate)), Settings.from_env({}))

    if accepted:
        assert asyncio.run(service.interpret(request)).status == "ready"
    else:
        with pytest.raises(InvalidModelOutputError):
            asyncio.run(service.interpret(request))


def test_missing_reschedule_target_is_cleared_even_if_model_invents_one() -> None:
    candidate = {
        "status": "ready",
        "intent": "reschedule",
        "title": None,
        "scheduled_at": "2026-03-06T18:00:00-05:00",
        "timezone": "America/New_York",
        "target_reference": "dentist reminder",
        "snooze_minutes": None,
        "clarification_questions": [],
        "user_message": "I can propose moving the dentist reminder.",
    }
    service = InterpretationService(FakeClient(json.dumps(candidate)), Settings.from_env({}))

    result = asyncio.run(
        service.interpret(make_request("Move it to Friday at 6 PM."))
    )

    assert result.status == "clarification_required"
    assert result.target_reference is None
    assert result.scheduled_at is None


def test_vague_reschedule_target_is_not_accepted_as_a_reference() -> None:
    candidate = {
        "status": "ready",
        "intent": "reschedule",
        "title": None,
        "scheduled_at": "2026-03-06T18:00:00-05:00",
        "timezone": "America/New_York",
        "target_reference": "later",
        "snooze_minutes": None,
        "clarification_questions": [],
        "user_message": "I can propose moving the reminder to Friday.",
    }
    service = InterpretationService(FakeClient(json.dumps(candidate)), Settings.from_env({}))

    result = asyncio.run(
        service.interpret(make_request("Move it to later."))
    )

    assert result.status == "clarification_required"
    assert result.target_reference is None


def test_missing_snooze_duration_is_cleared_even_if_model_invents_one() -> None:
    candidate = {
        "status": "ready",
        "intent": "snooze",
        "title": None,
        "scheduled_at": None,
        "timezone": "America/New_York",
        "target_reference": "meeting reminder",
        "snooze_minutes": 20,
        "clarification_questions": [],
        "user_message": "I can propose snoozing the meeting reminder.",
    }
    service = InterpretationService(FakeClient(json.dumps(candidate)), Settings.from_env({}))

    result = asyncio.run(
        service.interpret(make_request("Snooze my meeting reminder."))
    )

    assert result.status == "clarification_required"
    assert result.snooze_minutes is None


def test_private_reasoning_is_rejected_as_invalid_model_output() -> None:
    candidate = create_candidate("2026-03-02T17:00:00-05:00")
    candidate["user_message"] = "Here is my private chain of thought."
    service = InterpretationService(FakeClient(json.dumps(candidate)), Settings.from_env({}))

    with pytest.raises(InvalidModelOutputError):
        asyncio.run(
            service.interpret(
                make_request("Remind me to call Rahul tomorrow at 5 PM.")
            )
        )


@pytest.mark.parametrize(
    "message",
    [
        "I will call Rahul now.",
        "I've scheduled it.",
        "Your reminder has been set.",
        "Reminder created for tomorrow at 5 PM.",
        "Dentist reminder rescheduled to Friday.",
    ],
)
def test_external_action_claims_are_rejected(message: str) -> None:
    candidate = create_candidate("2026-03-02T17:00:00-05:00")
    candidate["user_message"] = message
    service = InterpretationService(FakeClient(json.dumps(candidate)), Settings.from_env({}))

    with pytest.raises(InvalidModelOutputError):
        asyncio.run(
            service.interpret(
                make_request("Remind me to call Rahul tomorrow at 5 PM.")
            )
        )


def test_unsupported_title_is_not_accepted_as_ready() -> None:
    candidate = create_candidate("2026-03-02T17:00:00-05:00")
    candidate["title"] = "Call Priya"
    service = InterpretationService(FakeClient(json.dumps(candidate)), Settings.from_env({}))

    with pytest.raises(InvalidModelOutputError):
        asyncio.run(
            service.interpret(make_request("Remind me to call Rahul tomorrow at 5 PM."))
        )


def test_scattered_words_do_not_ground_an_invented_title() -> None:
    candidate = create_candidate("2026-03-02T17:00:00-05:00")
    service = InterpretationService(FakeClient(json.dumps(candidate)), Settings.from_env({}))

    with pytest.raises(InvalidModelOutputError):
        asyncio.run(
            service.interpret(
                make_request("Remind me to call Priya tomorrow at 5 PM, and tell Rahul.")
            )
        )


def test_unsupported_target_is_not_accepted_as_ready() -> None:
    candidate = {
        "status": "ready", "intent": "snooze", "title": None,
        "scheduled_at": None, "timezone": "America/New_York",
        "target_reference": "dentist reminder", "snooze_minutes": 20,
        "clarification_questions": [], "user_message": "I propose snoozing it.",
    }
    service = InterpretationService(FakeClient(json.dumps(candidate)), Settings.from_env({}))

    with pytest.raises(InvalidModelOutputError):
        asyncio.run(
            service.interpret(make_request("Snooze my meeting reminder by 20 minutes."))
        )


@pytest.mark.parametrize("duration", [True, "20"])
def test_snooze_duration_rejects_non_integer_json_values(duration) -> None:
    candidate = {
        "status": "ready", "intent": "snooze", "title": None,
        "scheduled_at": None, "timezone": "America/New_York",
        "target_reference": "meeting reminder", "snooze_minutes": duration,
        "clarification_questions": [], "user_message": "I propose snoozing it.",
    }
    service = InterpretationService(FakeClient(json.dumps(candidate)), Settings.from_env({}))

    with pytest.raises(InvalidModelOutputError):
        asyncio.run(
            service.interpret(make_request("Snooze my meeting reminder by 20 minutes."))
        )


@pytest.mark.parametrize(
    "raw_output",
    [
        "not json",
        json.dumps({**create_candidate("2026-03-02T17:00:00-05:00"), "extra": "field"}),
        json.dumps({**create_candidate("2026-03-02T17:00:00-05:00"), "timezone": "UTC"}),
    ],
)
def test_invalid_or_mismatched_model_output_never_becomes_success(raw_output: str) -> None:
    service = InterpretationService(FakeClient(raw_output), Settings.from_env({}))

    with pytest.raises(InvalidModelOutputError):
        asyncio.run(
            service.interpret(
                make_request("Remind me to call Rahul tomorrow at 5 PM.")
            )
        )
