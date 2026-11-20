import json
from pathlib import Path

from fastapi.testclient import TestClient
import yaml

from reminder_agent.config import Settings
from reminder_agent.errors import (
    ApplicationError,
    InferenceTimeoutError,
    InvalidModelOutputError,
    ModelNotInstalledError,
    RuntimeUnavailableError,
)
from reminder_agent.api import create_app

CONTRACT_PATH = (
    Path(__file__).resolve().parents[2]
    / "specs"
    / "001-natural-language-reminder-agent"
    / "contracts"
    / "interpretation.openapi.yaml"
)


class FakeClient:
    def __init__(self, content: dict | Exception) -> None:
        self.content = content

    async def generate(self, _system: str, _user: str, _schema: dict) -> str:
        if isinstance(self.content, Exception):
            raise self.content
        return json.dumps(self.content)


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
        "user_message": "I can propose a reminder to call Rahul.",
    }


def request_body() -> dict:
    return {
        "text": "Remind me to call Rahul tomorrow at 5 PM.",
        "reference_datetime": "2026-03-01T09:00:00-05:00",
        "timezone": "America/New_York",
    }


def test_valid_response_uses_the_strict_interpretation_contract() -> None:
    app = create_app(Settings.from_env({}), FakeClient(valid_create()))

    response = TestClient(app).post("/v1/reminders/interpret", json=request_body())

    assert response.status_code == 200
    assert response.json() == valid_create()
    assert set(response.json()) == set(valid_create())


def test_fastapi_publishes_the_approved_openapi_contract() -> None:
    app = create_app(Settings.from_env({}), FakeClient(valid_create()))

    response = TestClient(app).get("/openapi.json")

    assert response.status_code == 200
    assert response.json() == yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_invalid_request_has_distinct_422_code() -> None:
    app = create_app(Settings.from_env({}), FakeClient(valid_create()))
    body = {**request_body(), "timezone": "Not/A_Zone"}

    response = TestClient(app).post("/v1/reminders/interpret", json=body)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_naive_reference_datetime_is_rejected() -> None:
    app = create_app(Settings.from_env({}), FakeClient(valid_create()))
    body = {**request_body(), "reference_datetime": "2026-03-01T09:00:00"}

    response = TestClient(app).post("/v1/reminders/interpret", json=body)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_missing_description_is_not_returned_as_ready() -> None:
    app = create_app(Settings.from_env({}), FakeClient(valid_create()))
    body = {**request_body(), "text": "Remind me tomorrow at 5 PM."}

    response = TestClient(app).post("/v1/reminders/interpret", json=body)

    assert response.status_code == 200
    assert response.json()["status"] == "clarification_required"
    assert response.json()["scheduled_at"] is None
    assert response.json()["title"] is None


def test_runtime_failures_map_to_distinct_api_errors() -> None:
    cases = [
        (RuntimeUnavailableError(), 503, "OLLAMA_UNAVAILABLE"),
        (ModelNotInstalledError(), 503, "MODEL_NOT_INSTALLED"),
        (InferenceTimeoutError(), 504, "INFERENCE_TIMEOUT"),
        (InvalidModelOutputError(), 502, "INVALID_MODEL_OUTPUT"),
        (ApplicationError(), 500, "APPLICATION_ERROR"),
    ]
    for error, status, code in cases:
        app = create_app(Settings.from_env({}), FakeClient(error))

        response = TestClient(app).post(
            "/v1/reminders/interpret", json=request_body()
        )

        assert response.status_code == status
        assert response.json()["error"]["code"] == code
