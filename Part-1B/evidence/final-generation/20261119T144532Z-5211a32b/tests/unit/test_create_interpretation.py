import asyncio
import json
from datetime import datetime

from reminder_agent.config import Settings
from reminder_agent.schemas import InterpretationRequest
from reminder_agent.service import InterpretationService


class FakeClient:
    def __init__(self, content: dict) -> None:
        self.content = content

    async def generate(self, system: str, user: str, schema: dict) -> str:
        return json.dumps(self.content)


def ready_create() -> dict:
    return {
        "status": "ready",
        "intent": "create",
        "title": "Call Rahul",
        "scheduled_at": "2026-03-02T17:00:00-05:00",
        "timezone": "America/New_York",
        "target_reference": None,
        "snooze_minutes": None,
        "clarification_questions": [],
        "user_message": "I can remind you to call Rahul on March 2 at 5 PM.",
    }


def test_complete_create_and_paraphrase_are_interpreted() -> None:
    content = ready_create()
    service = InterpretationService(FakeClient(content), Settings.from_env({}))
    reference = datetime.fromisoformat("2026-03-01T09:00:00-05:00")
    first = asyncio.run(
        service.interpret(
            InterpretationRequest(
                text="Remind me to call Rahul tomorrow at 5 PM.",
                reference_datetime=reference,
                timezone="America/New_York",
            )
        )
    )
    second = asyncio.run(
        service.interpret(
            InterpretationRequest(
                text="Please remind me to phone Rahul tomorrow at 5 PM.",
                reference_datetime=reference,
                timezone="America/New_York",
            )
        )
    )
    assert first.intent == second.intent == "create"
    assert first.title == second.title == "Call Rahul"
    assert first.scheduled_at == second.scheduled_at


def test_model_cannot_make_create_ready_without_exact_time() -> None:
    service = InterpretationService(FakeClient(ready_create()), Settings.from_env({}))
    result = asyncio.run(
        service.interpret(
            InterpretationRequest(
                text="Remind me to call Rahul tomorrow.",
                reference_datetime=datetime.fromisoformat("2026-03-01T09:00:00-05:00"),
                timezone="America/New_York",
            )
        )
    )
    assert result.status == "clarification_required"
    assert result.scheduled_at is None
    assert result.clarification_questions
