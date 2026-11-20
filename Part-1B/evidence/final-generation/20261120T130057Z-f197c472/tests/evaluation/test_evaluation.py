import asyncio
import importlib.util
import json
from collections import Counter
from pathlib import Path

import pytest
import yaml

from reminder_agent.evaluation import (
    DatasetValidationError,
    aggregate_scores,
    evaluate_case_run,
    incomplete_reason,
    validate_dataset,
)
from reminder_agent.config import Settings
from reminder_agent.prompts import load_prompt_bundle


ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "evals" / "dataset.json"
CONTRACT_PATH = (
    ROOT
    / "specs"
    / "001-natural-language-reminder-agent"
    / "contracts"
    / "interpretation.openapi.yaml"
)


def test_baseline_dataset_has_nineteen_mapped_cases_and_required_distribution() -> None:
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))

    validate_dataset(dataset)

    counts = Counter(case["category"] for case in dataset["cases"])
    assert counts == {
        "representative": 5,
        "boundary": 4,
        "ambiguous/missing": 4,
        "malformed": 2,
        "adversarial/guardrail": 4,
    }
    assert len(dataset["cases"]) == 19
    assert len({case["case_id"] for case in dataset["cases"]}) == 19
    assert all(case["fr_ids"] and case["ac_ids"] for case in dataset["cases"])


def test_dataset_validation_rejects_missing_traceability() -> None:
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    dataset["cases"][0]["ac_ids"] = []

    with pytest.raises(DatasetValidationError):
        validate_dataset(dataset)


def test_safe_application_clarification_does_not_mask_model_invention() -> None:
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    case = next(item for item in dataset["cases"] if item["case_id"] == "AMB-001")
    contract = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
    schema = contract["components"]["schemas"]["InterpretationResult"]
    generated = {
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
    application_output = {
        "status": "clarification_required",
        "intent": "create",
        "title": None,
        "scheduled_at": None,
        "timezone": "America/New_York",
        "target_reference": None,
        "snooze_minutes": None,
        "clarification_questions": ["What should I remind you about?"],
        "user_message": "What should I remind you about?",
    }

    result = evaluate_case_run(
        case, application_output, schema, model_candidate=generated
    )

    assert result["structural_pass"]
    assert result["semantic"]["score"] == 100
    critical = {item["name"]: item["passed"] for item in result["critical_assertions"]}
    assert not critical["no_invented_detail"]
    assert not critical["no_ready_without_mandatory_fields"]


@pytest.mark.parametrize(
    ("title", "target", "expected_invention_check"),
    [
        (None, None, True),
        ("Call Priya", None, False),
        (None, "call Rahul", True),
        (None, "dentist reminder", False),
    ],
)
def test_missing_expected_detail_is_not_invention_but_wrong_details_are(
    title, target, expected_invention_check
) -> None:
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    case = next(item for item in dataset["cases"] if item["case_id"] == "AMB-002")
    schema = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))[
        "components"
    ]["schemas"]["InterpretationResult"]
    candidate = {
        "status": "clarification_required", "intent": "create", "title": title,
        "scheduled_at": None, "timezone": case["timezone"], "target_reference": target,
        "snooze_minutes": None, "clarification_questions": ["What time?"],
        "user_message": "What time?",
    }

    result = evaluate_case_run(case, candidate, schema, model_candidate=candidate)

    checks = {item["name"]: item["passed"] for item in result["critical_assertions"]}
    assert checks["no_invented_detail"] is expected_invention_check
    assert checks["no_ready_without_mandatory_fields"]


@pytest.mark.parametrize(
    ("case_id", "scheduled_at", "invariant"),
    [
        ("BND-003", "2026-03-08T03:30:00-04:00", "no_nonexistent_time_ready"),
        ("BND-004", "2026-11-01T01:30:00-04:00", "no_ambiguous_time_ready"),
    ],
)
def test_safe_clarification_does_not_mask_invalid_dst_candidate(
    case_id, scheduled_at, invariant
) -> None:
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    case = next(item for item in dataset["cases"] if item["case_id"] == case_id)
    schema = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))[
        "components"
    ]["schemas"]["InterpretationResult"]
    candidate = {
        "status": "ready", "intent": "create", "title": "Call the clinic",
        "scheduled_at": scheduled_at, "timezone": case["timezone"],
        "target_reference": None, "snooze_minutes": None,
        "clarification_questions": [], "user_message": "Proposed reminder.",
    }
    application = {
        **candidate, "status": "clarification_required", "scheduled_at": None,
        "clarification_questions": ["Which time should I use?"],
        "user_message": "Which time should I use?",
    }

    result = evaluate_case_run(case, application, schema, model_candidate=candidate)

    checks = {item["name"]: item["passed"] for item in result["critical_assertions"]}
    assert not checks[invariant]


def test_aggregate_uses_equal_case_run_property_weighting() -> None:
    result = aggregate_scores(
        [
            {
                "structural_pass": True,
                "critical_assertions": [{"passed": True}],
                "property_assertions": [{"passed": True}],
                "semantic": {"score": 100},
            },
            {
                "structural_pass": True,
                "critical_assertions": [{"passed": True}],
                "property_assertions": [{"passed": True}, {"passed": False}],
                "semantic": {"score": 100},
            },
        ]
    )

    assert result["property_invariant"] == 75


def test_aggregate_uses_the_approved_weighting_formula_and_gates() -> None:
    result = aggregate_scores(
        [
            {
                "structural_pass": True,
                "critical_assertions": [{"passed": True}],
                "property_assertions": [{"passed": True}],
                "semantic": {"score": 100},
            }
        ]
    )

    assert result["aggregate"] == 100
    assert result["passed"]


def test_threshold_formula_and_infrastructure_classification_are_fixed() -> None:
    contract = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert contract["x-runtime-configuration"]["temperature-environment-variable"][
        "default"
    ] == 0.2
    assert incomplete_reason(["OLLAMA_UNAVAILABLE"]) == "BLOCKED_INFRASTRUCTURE"
    assert incomplete_reason(["INFERENCE_TIMEOUT"]) == "BLOCKED_INFRASTRUCTURE"
    assert incomplete_reason(["APPLICATION_ERROR"]) == "APPLICATION_ERROR"
    assert incomplete_reason(["INVALID_MODEL_OUTPUT"]) is None


def test_rejected_candidate_is_not_recorded_as_application_response(monkeypatch) -> None:
    module_spec = importlib.util.spec_from_file_location(
        "evaluation_runner", ROOT / ".harness" / "run_evaluation.py"
    )
    assert module_spec is not None and module_spec.loader is not None
    runner = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(runner)

    class FakeClient:
        def __init__(self, _settings):
            pass

        async def generate_with_metadata(self, _system, _user, _schema):
            return json.dumps({
                "status": "ready", "intent": "create", "title": "Call Rahul",
                "scheduled_at": "2026-03-02T17:00:00-05:00",
                "timezone": "America/New_York", "target_reference": None,
                "snooze_minutes": None, "clarification_questions": [],
                "user_message": "Reminder created for tomorrow.",
            }), {"http_status": 200}

        async def aclose(self):
            pass

    monkeypatch.setattr(runner, "OllamaClient", FakeClient)
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    runs, attempted, completed, _ = asyncio.run(
        runner._run_generations(
            {"cases": [dataset["cases"][0]]}, Settings.from_env({}), load_prompt_bundle()
        )
    )
    assert attempted == completed == 3
    assert all(r["error_code"] == "INVALID_MODEL_OUTPUT" for r in runs)
    assert all(r["output"] is None and r["generated_output"] is not None for r in runs)
    assert all(not r["structural_pass"] for r in runs)
