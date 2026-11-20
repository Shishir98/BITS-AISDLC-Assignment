from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import urllib.request
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from smart_todo.app import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[2]
POWERSHELL = os.environ.get("POWERSHELL_EXE", "powershell.exe")

REQUIRED_GOVERNING_SPEC_PATHS = {
    "specs/001-smart-todo-api/checklists/requirements.md",
    "specs/001-smart-todo-api/contracts/openapi.yaml",
    "specs/001-smart-todo-api/data-model.md",
    "specs/001-smart-todo-api/plan.md",
    "specs/001-smart-todo-api/quickstart.md",
    "specs/001-smart-todo-api/research.md",
    "specs/001-smart-todo-api/spec.md",
    "specs/001-smart-todo-api/tasks.md",
    "specs/001-smart-todo-api/test-strategy.md",
}


def test_at022_required_checks_and_in_process_test_client_are_network_independent(
    tmp_path: Path,
) -> None:
    config = json.loads((PROJECT_ROOT / ".harness" / "mandatory-checks.json").read_text(encoding="utf-8"))
    assert config["authority"]["trustedRunnerPresent"] is False
    assert config["authority"]["d01Status"] == "SCOPED_WAIVER"
    assert config["authority"]["githubWorkflowCandidatePresent"] is True
    assert config["authority"]["githubWorkflowRunVerified"] is False
    assert config["ownerDisposition"]["customBootstrapStatus"] == "WAIVED"
    assert config["ownerDisposition"]["waivedPortions"] == [
        "AC-023.canonical-protected-runner-and-baseline",
        "AC-024.actual-protected-approval-register",
    ]
    assert config["executionSequence"] == [
        "candidate-integrity-before",
        "instruction-inventory",
        "d01-owner-disposition",
        "protected-workflow-verification",
        "persistence-contract-readiness",
        "ruff",
        "bandit",
        "pytest-and-traceability",
        "repository-hygiene",
        "human-security-review",
        "human-final-decision",
        "candidate-integrity-after",
        "root-workflow-integrity-after",
    ]
    assert set(config["pytest"]["acceptanceTestIds"]) == {
        f"AT-{number:03d}" for number in range(1, 30)
    }

    # Verify offline and proxy isolation environment variables are active
    assert os.environ.get("PIP_NO_INDEX") == "1"
    assert os.environ.get("UV_OFFLINE") == "1"
    assert os.environ.get("PYTHONNOUSERSITE") == "1"
    assert os.environ.get("UV_NO_CONFIG") == "1"
    assert os.environ.get("HTTP_PROXY") == "http://127.0.0.1:9"
    assert os.environ.get("HTTPS_PROXY") == "http://127.0.0.1:9"
    assert os.environ.get("ALL_PROXY") == "http://127.0.0.1:9"

    # Verify external TCP connect, connect_ex, create_connection, UDP sendto, DNS getaddrinfo, and HTTP urlopen are blocked
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp_sock:
        with pytest.raises(RuntimeError, match="External network access is disabled"):
            tcp_sock.connect(("93.184.216.34", 80))
        with pytest.raises(RuntimeError, match="External network access is disabled"):
            tcp_sock.connect_ex(("93.184.216.34", 80))

    with pytest.raises(RuntimeError, match="External network access is disabled"):
        socket.create_connection(("example.com", 443))

    with (
        socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_sock,
        pytest.raises(RuntimeError, match="External network access is disabled"),
    ):
        udp_sock.sendto(b"ping", ("8.8.8.8", 53))

    with pytest.raises(RuntimeError, match="External DNS resolution is disabled"):
        socket.getaddrinfo("example.com", 80)

    with pytest.raises(RuntimeError, match="External HTTP access is disabled"):
        urllib.request.urlopen("https://example.com/tasks")

    # Verify in-process ASGI TestClient continues to operate deterministically without external network
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


def test_at024_instruction_inventory_is_exact_and_current() -> None:
    inventory = json.loads(
        (PROJECT_ROOT / ".harness" / "instruction-files.json").read_text(encoding="utf-8")
    )
    assert isinstance(inventory, list)
    assert len(inventory) == 19
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
    assert REQUIRED_GOVERNING_SPEC_PATHS <= {entry["path"] for entry in inventory}


def test_at027_human_security_review_is_a_separate_unverified_gate() -> None:
    runner = (PROJECT_ROOT / ".harness" / "run.ps1").read_text(encoding="utf-8")
    assert '"human-security-review"' in runner
    assert '"human-final-decision"' in runner
    assert "Human security-review action T044 remains" in runner
    assert "Human final-decision action T045 remains" in runner
    assert "The runner does not create, infer, or impersonate these records" in runner


def test_at028_runner_does_not_create_or_infer_acceptance_decisions() -> None:
    runner = (PROJECT_ROOT / ".harness" / "run.ps1").read_text(encoding="utf-8")
    assert "decision = $null" in runner
    assert "The runner does not create, infer, or impersonate these records" in runner
    assert '"human-final-decision"' in runner
