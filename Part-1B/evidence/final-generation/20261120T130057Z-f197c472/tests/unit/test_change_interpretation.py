import asyncio
import json
from datetime import datetime

import pytest

from reminder_agent.config import Settings
from reminder_agent.schemas import InterpretationRequest
from reminder_agent.service import InterpretationService


class FakeClient:
    def __init__(self, content: dict) -> None:
        self.content = content

    async def generate(self, system: str, user: str, schema: dict) -> str:
        return json.dumps(self.content)


@pytest.mark.parametrize(
    ("content", "text", "intent"),
    [
        (
            {
                "status": "ready", "intent": "reschedule", "title": None,
                "scheduled_at": "2026-03-06T18:00:00-05:00",
                "timezone": "America/New_York", "target_reference": "dentist reminder",
                "snooze_minutes": None, "clarification_questions": [],
                "user_message": "The dentist reminder can move to Friday at 6 PM.",
            },
            "Move my dentist reminder to Friday at 6 PM.",
            "reschedule",
        ),
        (
            {
                "status": "ready", "intent": "snooze", "title": None,
                "scheduled_at": None, "timezone": "America/New_York",
                "target_reference": "meeting reminder", "snooze_minutes": 20,
                "clarification_questions": [],
                "user_message": "Snooze the meeting reminder for 20 minutes.",
            },
            "Snooze my meeting reminder by 20 minutes.",
            "snooze",
        ),
    ],
)
def test_ready_change_intents(content, text, intent) -> None:
    service = InterpretationService(FakeClient(content), Settings.from_env({}))
    result = asyncio.run(
        service.interpret(
            InterpretationRequest(
                text=text,
                reference_datetime=datetime.fromisoformat("2026-03-01T09:00:00-05:00"),
                timezone="America/New_York",
            )
        )
    )
    assert result.status == "ready"
    assert result.intent == intent


def test_missing_reschedule_target_is_not_actionable() -> None:
    content = {
        "status": "clarification_required", "intent": "reschedule", "title": None,
        "scheduled_at": None, "timezone": "America/New_York",
        "target_reference": None, "snooze_minutes": None,
        "clarification_questions": ["Which reminder should I move?"],
        "user_message": "I need the reminder to move.",
    }
    service = InterpretationService(FakeClient(content), Settings.from_env({}))
    result = asyncio.run(
        service.interpret(
            InterpretationRequest(
                text="Move it to Friday at 6 PM.",
                reference_datetime=datetime.fromisoformat("2026-03-01T09:00:00-05:00"),
                timezone="America/New_York",
            )
        )
    )
    assert result.status == "clarification_required"
    assert result.target_reference is None
