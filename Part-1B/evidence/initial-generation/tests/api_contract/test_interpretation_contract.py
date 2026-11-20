import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

from reminder_agent.schemas import InterpretationResult


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "specs" / "001-natural-language-reminder-agent" / "contracts" / "interpretation.openapi.yaml"


def load_result_schema() -> dict:
    contract = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
    return contract["components"]["schemas"]["InterpretationResult"]


def valid_create() -> dict:
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


def test_contract_schema_is_valid_and_accepts_complete_create() -> None:
    schema = load_result_schema()
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(valid_create())
    InterpretationResult.model_validate(valid_create())


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.update(extra="not allowed"),
        lambda value: value.update(status="complete"),
        lambda value: value.update(scheduled_at="2026-03-02T17:00:00"),
        lambda value: value.update(title=None),
        lambda value: value.update(snooze_minutes=1),
    ],
)
def test_contract_rejects_invalid_create_relationships(mutate) -> None:
    payload = valid_create()
    mutate(payload)
    schema = load_result_schema()
    with pytest.raises(Exception):
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)
    with pytest.raises(ValidationError):
        InterpretationResult.model_validate(payload)


def test_success_response_has_exactly_nine_fields() -> None:
    payload = valid_create()
    assert set(payload) == set(InterpretationResult.model_fields)
    assert json.loads(InterpretationResult.model_validate(payload).model_dump_json()) == payload
