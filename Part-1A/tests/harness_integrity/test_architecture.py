from __future__ import annotations

import ast
import json
from pathlib import Path

from smart_todo.api import errors
from smart_todo.app import create_app
from smart_todo.domain.ports import TaskRepository

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE = PROJECT_ROOT / "src" / "smart_todo"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_at025_runtime_versions_repository_port_and_layer_boundaries(tmp_path: Path) -> None:
    project = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'requires-python = ">=3.12,<3.13"' in project
    assert "fastapi" in project
    assert "pydantic" in project
    assert isinstance(TaskRepository, type)
    assert getattr(TaskRepository, "_is_protocol", False) is True
    assert callable(TaskRepository.load)
    assert callable(TaskRepository.save)
    assert create_app(tmp_path / "runtime.json").title == "Smart Todo API"

    domain_imports = set().union(*(_imports(path) for path in (SOURCE / "domain").glob("*.py")))
    assert not any("smart_todo.persistence" in name for name in domain_imports)
    assert not any(name.endswith(".persistence.errors") for name in domain_imports)
    assert any("TaskRepository" in path.read_text(encoding="utf-8") for path in (SOURCE / "domain").glob("*.py"))
    assert "smart_todo.persistence" not in _imports(SOURCE / "api" / "routes.py")
    app = create_app(tmp_path / "runtime.json")
    assert errors.persistence_exception_handler in app.exception_handlers.values()
    assert errors.malformed_store_exception_handler in app.exception_handlers.values()


def test_candidate_controls_keep_protected_trust_and_human_records_unavailable() -> None:
    controls = json.loads((PROJECT_ROOT / ".harness" / "mandatory-checks.json").read_text(encoding="utf-8"))
    runner = (PROJECT_ROOT / ".harness" / "run.ps1").read_text(encoding="utf-8")
    assert controls["authority"]["trustedRunnerPresent"] is False
    assert controls["authority"]["protectedBaselinePresent"] is False
    assert controls["authority"]["d01Status"] == "BLOCKED"
    assert controls["persistenceContractReadiness"]["d05Status"] == "RESOLVED_BY_APPROVED_SPEC_AMENDMENT"
    assert controls["persistenceContractReadiness"]["approvedSpecVersion"] == "1.4.0"
    assert controls["persistenceContractReadiness"]["humanApprovalDate"] == "2026-11-13"
    assert controls["persistenceContractReadiness"]["applicationHandledRecoveryContractApproved"] is True
    assert controls["persistenceContractReadiness"]["atomicVisibilityGuaranteed"] is False
    assert controls["persistenceContractReadiness"]["crashDurabilityGuaranteed"] is False
    assert controls["persistenceContractReadiness"]["rollbackTestsEstablishAtomicVisibility"] is False
    assert controls["persistenceContractReadiness"]["evidenceReferences"] == []
    assert "human-review-and-decision" in controls["executionSequence"]
    assert controls["authority"]["githubWorkflowCandidatePresent"] is True
    assert controls["authority"]["githubWorkflowRunVerified"] is False
    assert '"persistence-contract-readiness"' in runner
    assert "RESOLVED_BY_APPROVED_SPEC_AMENDMENT" in runner
