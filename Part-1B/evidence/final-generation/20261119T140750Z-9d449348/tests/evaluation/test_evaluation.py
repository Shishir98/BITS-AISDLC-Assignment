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
