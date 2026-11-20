import json
from collections import Counter
from pathlib import Path

import pytest
import yaml

from reminder_agent.evaluation import (
    DatasetValidationError,
    aggregate_scores,
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


def test_threshold_formula_and_infrastructure_classification_are_fixed() -> None:
    contract = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert contract["x-runtime-configuration"]["temperature-environment-variable"][
        "default"
    ] == 0.2
    assert incomplete_reason(["OLLAMA_UNAVAILABLE"]) == "BLOCKED_INFRASTRUCTURE"
    assert incomplete_reason(["INFERENCE_TIMEOUT"]) == "BLOCKED_INFRASTRUCTURE"
    assert incomplete_reason(["APPLICATION_ERROR"]) == "APPLICATION_ERROR"
    assert incomplete_reason(["INVALID_MODEL_OUTPUT"]) is None
