from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from smart_todo.app import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[2]
POWERSHELL = os.environ.get("POWERSHELL_EXE", "powershell.exe")


def test_at022_required_checks_and_in_process_test_client_are_network_independent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = json.loads((PROJECT_ROOT / ".harness" / "mandatory-checks.json").read_text(encoding="utf-8"))
    assert config["authority"]["trustedRunnerPresent"] is False
    assert config["authority"]["d01Status"] == "BLOCKED"
    assert config["authority"]["githubWorkflowCandidatePresent"] is True
    assert config["authority"]["githubWorkflowRunVerified"] is False
    assert config["executionSequence"] == [
        "candidate-integrity-before",
        "instruction-inventory",
        "governance-boundary",
        "persistence-contract-readiness",
        "ruff",
        "bandit",
        "pytest-and-traceability",
        "repository-hygiene",
        "human-review-and-decision",
        "candidate-integrity-after",
    ]
    assert set(config["pytest"]["acceptanceTestIds"]) == {
        f"AT-{number:03d}" for number in range(1, 30)
    }

    original_connect = __import__("socket").socket.connect

    def reject_external_network(sock: object, address: object) -> None:
        host = address[0] if isinstance(address, tuple) and address else ""
        if host not in ("127.0.0.1", "::1", "localhost"):
            raise AssertionError("API contract tests must not contact external hosts")
        original_connect(sock, address)

    monkeypatch.setattr("socket.socket.connect", reject_external_network)
    client = TestClient(create_app(tmp_path / "tasks.json"))
    assert client.get("/tasks").status_code == 200


def test_at023_untrusted_repository_runner_refuses_authoritative_mode(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(PROJECT_ROOT / ".harness" / "run.ps1"),
            "-ProjectRoot",
            str(PROJECT_ROOT),
            "-EvidenceRoot",
            str(tmp_path / "evidence"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "untrusted candidate" in result.stderr.lower()
    assert "d-01" in result.stderr.lower()
    assert not (tmp_path / "evidence").exists()


def test_at024_instruction_inventory_is_exact_and_unapproved_changes_remain_blocked() -> None:
    inventory = json.loads(
        (PROJECT_ROOT / ".harness" / "instruction-files.json").read_text(encoding="utf-8")
    )
    assert isinstance(inventory, list)
    required_keys = {"path", "purpose", "classification", "sha256", "approval_reference"}
    seen: set[str] = set()
    for entry in inventory:
        assert set(entry) == required_keys
        path = entry["path"]
        assert isinstance(path, str) and "*" not in path and "?" not in path
        normalized = path.replace("\\", "/").lower()
        assert normalized not in seen
        seen.add(normalized)
        actual = hashlib.sha256((PROJECT_ROOT / path).read_bytes()).hexdigest()
        assert actual == entry["sha256"]
        assert entry["approval_reference"] in ("", None)
    assert inventory


def test_at027_human_security_review_is_a_separate_blocked_gate() -> None:
    runner = (PROJECT_ROOT / ".harness" / "run.ps1").read_text(encoding="utf-8")
    assert '"human-review-and-decision"' in runner
    assert "No human security disposition or final decision was supplied" in runner
    assert "The runner does not create, infer, or impersonate these records" in runner


def test_at028_runner_does_not_create_or_infer_acceptance_decisions() -> None:
    runner = (PROJECT_ROOT / ".harness" / "run.ps1").read_text(encoding="utf-8")
    assert "decision = $null" in runner
    assert "The runner does not create, infer, or impersonate these records" in runner
    assert "human-review-and-decision" in runner
