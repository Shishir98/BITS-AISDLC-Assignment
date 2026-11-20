from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = PROJECT_ROOT.parent
WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "part-1a-candidate-validation.yml"
PREPARE_SCRIPT = PROJECT_ROOT / ".harness" / "trust" / "prepare_candidate.py"
RUN_VALIDATION_SCRIPT = PROJECT_ROOT / ".harness" / "trust" / "run_validation.py"
SEAL_SCRIPT = PROJECT_ROOT / ".harness" / "trust" / "seal_evidence.py"


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    _write(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def _make_approved_fixture(root: Path) -> tuple[Path, Path, Path, str]:
    trusted_repo = root / "trusted"
    trusted_project = trusted_repo / "Part-1A"
    candidate_repo = root / "candidate"
    candidate_project = candidate_repo / "Part-1A"
    script_content = PREPARE_SCRIPT.read_text(encoding="utf-8")
    _write(trusted_repo / ".github" / "workflows" / "part-1a-candidate-validation.yml", "name: fixture\n")
    _write(trusted_project / ".harness" / "mandatory-checks.json", "{}\n")
    _write(trusted_project / ".harness" / "trust" / "prepare_candidate.py", script_content)
    _write(
        trusted_project / ".harness" / "trust" / "run_validation.py",
        RUN_VALIDATION_SCRIPT.read_text(encoding="utf-8"),
    )
    _write(
        trusted_project / ".harness" / "trust" / "seal_evidence.py",
        SEAL_SCRIPT.read_text(encoding="utf-8"),
    )
    _write(trusted_project / "pyproject.toml", "[project]\nname = 'fixture'\n")
    _write(trusted_project / "uv.lock", "version = 1\n")
    _write(trusted_project / "tests" / "test_control.py", "def test_fixture():\n    assert True\n")

    inventory = []
    for index in range(10):
        relative = f".specify/instruction-{index:02}.md"
        _write(trusted_project / relative, f"Approved fixture instruction {index}\n")
        inventory.append(
            {
                "path": relative,
                "purpose": f"Synthetic fixture instruction {index}",
                "classification": "instruction",
                "sha256": _sha256(trusted_project / relative),
                "approval_reference": "synthetic-review-reference",
            }
        )
    _write_json(trusted_project / ".harness" / "instruction-files.json", inventory)

    baseline_paths = {
        entry["path"]
        for entry in inventory
    } | {
        ".harness/instruction-files.json",
        ".harness/mandatory-checks.json",
        ".harness/trust/prepare_candidate.py",
        ".harness/trust/run_validation.py",
        ".harness/trust/seal_evidence.py",
        "pyproject.toml",
        "tests/test_control.py",
        "uv.lock",
    }
    files = [
        {"path": relative, "sha256": _sha256(trusted_project / relative)}
        for relative in sorted(baseline_paths)
    ]
    trusted_files = [
        {
            "path": ".github/workflows/part-1a-candidate-validation.yml",
            "sha256": _sha256(trusted_repo / ".github" / "workflows" / "part-1a-candidate-validation.yml"),
        },
        {
            "path": "Part-1A/.harness/trust/prepare_candidate.py",
            "sha256": _sha256(trusted_project / ".harness" / "trust" / "prepare_candidate.py"),
        },
        {
            "path": "Part-1A/.harness/trust/run_validation.py",
            "sha256": _sha256(trusted_project / ".harness" / "trust" / "run_validation.py"),
        },
        {
            "path": "Part-1A/.harness/trust/seal_evidence.py",
            "sha256": _sha256(trusted_project / ".harness" / "trust" / "seal_evidence.py"),
        },
    ]
    baseline = {
        "schemaVersion": 1,
        "status": "BOOTSTRAP_PENDING_HUMAN_REVIEW",
        "files": files,
        "trusted_files": trusted_files,
    }
    baseline_path = trusted_project / ".harness" / "trust" / "bootstrap-baseline.json"
    _write_json(baseline_path, baseline)
    register = {
        "schemaVersion": 1,
        "status": "APPROVED",
        "baseline_sha256": _sha256(baseline_path),
        "instruction_files": inventory,
        "approval": {
            "decision": "APPROVE",
            "approver": "synthetic test fixture",
            "approved_at": "2026-01-01T00:00:00Z",
            "rationale": "Synthetic disposable approval fixture only",
            "source_commit": "a" * 40,
            "approval_reference": "synthetic-review-reference",
        },
    }
    register_path = trusted_project / ".harness" / "trust" / "approval-register.json"
    _write_json(register_path, register)

    shutil.copytree(trusted_project, candidate_project)
    subprocess.run(["git", "init", str(candidate_repo)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(candidate_repo), "config", "user.name", "Fixture"], check=True)
    subprocess.run(["git", "-C", str(candidate_repo), "config", "user.email", "fixture@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(candidate_repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(candidate_repo), "commit", "-m", "synthetic candidate"], check=True, capture_output=True)
    commit = subprocess.run(
        ["git", "-C", str(candidate_repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return trusted_repo, trusted_project, candidate_project, commit


def _make_writable(root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_file():
            path.chmod(0o644)
        elif path.is_dir():
            path.chmod(0o755)
    root.chmod(0o755)


def test_at022_workflow_uses_protected_main_read_only_checkout_and_sha() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow
    assert "candidate_sha:" in workflow
    assert "if: github.ref == 'refs/heads/main'" in workflow
    assert "permissions:\n  contents: read" in workflow
    assert workflow.count("uses: actions/checkout@v4") == 2
    assert "path: trusted" in workflow
    assert "path: candidate" in workflow
    assert "ref: ${{ github.workflow_sha }}" in workflow
    assert workflow.count("persist-credentials: false") == 2
    assert "secrets." not in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "prepare_candidate.py" in workflow
    assert "run_validation.py" in workflow
    assert "Seal and verify evidence bundle" in workflow


def test_at022_candidate_process_receives_only_allowlisted_environment(tmp_path: Path) -> None:
    sys.path.insert(0, str(PREPARE_SCRIPT.parent))
    try:
        module = _load_module(RUN_VALIDATION_SCRIPT, "run_validation_environment_test")
    finally:
        sys.path.pop(0)
    inherited = {
        "PATH": r"C:\Windows\System32",
        "SYSTEMROOT": r"C:\Windows",
        "GITHUB_TOKEN": "DUMMY",
        "ACTIONS_RUNTIME_TOKEN": "DUMMY",
        "GITHUB_ENV": r"C:\runner\environment",
        "UV_INDEX_URL": "DUMMY",
    }

    environment = module._candidate_environment(
        tmp_path / "stage",
        tmp_path / "evidence",
        tmp_path / "venv",
        tmp_path / "uv-cache",
        inherited,
    )
    assert environment["PATH"] == inherited["PATH"]
    assert environment["SYSTEMROOT"] == inherited["SYSTEMROOT"]
    assert environment["UV_NO_CONFIG"] == "1"
    assert environment["PYTHONNOUSERSITE"] == "1"
    assert not {"GITHUB_TOKEN", "ACTIONS_RUNTIME_TOKEN", "GITHUB_ENV", "UV_INDEX_URL"} & environment.keys()


def test_at023_pending_bootstrap_fails_before_candidate_staging(tmp_path: Path) -> None:
    script = _load_module(PREPARE_SCRIPT, "prepare_candidate_pending")
    stage = tmp_path / "stage"
    evidence = tmp_path / "evidence"
    args = SimpleNamespace(
        candidate_sha="a" * 40,
        trusted_root=str(PROJECT_ROOT),
        trusted_repo_root=str(REPOSITORY_ROOT),
        candidate_root=str(PROJECT_ROOT),
        stage=str(stage),
        evidence=str(evidence),
        github_output=None,
    )
    assert script.prepare(args) == 2
    report = json.loads((evidence / "bootstrap-preflight.json").read_text(encoding="utf-8"))
    assert report["status"] == "BLOCKED"
    assert "pending human review" in report["reason"]
    assert not stage.exists()
    assert not (evidence / "candidate-manifest.json").exists()


def test_at023_synthetic_tampered_test_file_is_rejected_before_staging(tmp_path: Path) -> None:
    script = _load_module(PREPARE_SCRIPT, "prepare_candidate_tamper")
    trusted_repo, trusted_project, candidate_project, commit = _make_approved_fixture(tmp_path)
    test_file = candidate_project / "tests" / "test_control.py"
    test_file.write_text("raise RuntimeError('must not execute')\n", encoding="utf-8")
    stage = tmp_path / "tampered-stage"
    evidence = tmp_path / "tampered-evidence"
    args = SimpleNamespace(
        candidate_sha=commit,
        trusted_root=str(trusted_project),
        trusted_repo_root=str(trusted_repo),
        candidate_root=str(candidate_project),
        stage=str(stage),
        evidence=str(evidence),
        github_output=None,
    )
    assert script.prepare(args) == 2
    report = json.loads((evidence / "bootstrap-preflight.json").read_text(encoding="utf-8"))
    assert report["status"] == "BLOCKED"
    assert "Candidate control/test digest mismatch" in report["reason"]
    assert not stage.exists()


def test_at023_unapproved_changes_to_controls_inventory_instructions_and_dependencies_are_rejected(
    tmp_path: Path,
) -> None:
    script = _load_module(PREPARE_SCRIPT, "prepare_candidate_multiple_tamper")
    trusted_repo, trusted_project, candidate_project, commit = _make_approved_fixture(tmp_path)
    paths = (
        "tests/test_control.py",
        ".harness/mandatory-checks.json",
        ".harness/trust/prepare_candidate.py",
        ".harness/instruction-files.json",
        ".specify/instruction-00.md",
        "pyproject.toml",
        "uv.lock",
    )
    for index, relative in enumerate(paths):
        candidate_file = candidate_project / relative
        original = candidate_file.read_bytes()
        candidate_file.write_bytes(original + b"\ntampered\n")
        evidence = tmp_path / f"tampered-evidence-{index}"
        stage = tmp_path / f"tampered-stage-{index}"
        args = SimpleNamespace(
            candidate_sha=commit,
            trusted_root=str(trusted_project),
            trusted_repo_root=str(trusted_repo),
            candidate_root=str(candidate_project),
            stage=str(stage),
            evidence=str(evidence),
            github_output=None,
        )
        assert script.prepare(args) == 2, relative
        report = json.loads((evidence / "bootstrap-preflight.json").read_text(encoding="utf-8"))
        assert report["status"] == "BLOCKED", relative
        assert not stage.exists(), relative
        candidate_file.write_bytes(original)


def test_at024_tampered_trusted_workflow_or_approval_register_is_rejected(tmp_path: Path) -> None:
    script = _load_module(PREPARE_SCRIPT, "prepare_candidate_trusted_tamper")
    trusted_repo, trusted_project, candidate_project, commit = _make_approved_fixture(tmp_path)
    workflow = trusted_repo / ".github" / "workflows" / "part-1a-candidate-validation.yml"
    original = workflow.read_bytes()
    workflow.write_bytes(original + b"# tampered\n")
    args = SimpleNamespace(
        candidate_sha=commit,
        trusted_root=str(trusted_project),
        trusted_repo_root=str(trusted_repo),
        candidate_root=str(candidate_project),
        stage=str(tmp_path / "workflow-tampered-stage"),
        evidence=str(tmp_path / "workflow-tampered-evidence"),
        github_output=None,
    )
    assert script.prepare(args) == 2
    report = json.loads(
        (tmp_path / "workflow-tampered-evidence" / "bootstrap-preflight.json").read_text(encoding="utf-8")
    )
    assert "Trusted control digest mismatch" in report["reason"]
    workflow.write_bytes(original)

    register_path = trusted_project / ".harness" / "trust" / "approval-register.json"
    register = json.loads(register_path.read_text(encoding="utf-8"))
    register["baseline_sha256"] = "0" * 64
    _write_json(register_path, register)
    args.stage = str(tmp_path / "approval-tampered-stage")
    args.evidence = str(tmp_path / "approval-tampered-evidence")
    assert script.prepare(args) == 2
    report = json.loads(
        (tmp_path / "approval-tampered-evidence" / "bootstrap-preflight.json").read_text(encoding="utf-8")
    )
    assert "baseline digest does not match" in report["reason"]
    assert not Path(args.stage).exists()


def test_at023_verified_candidate_is_staged_and_manifest_tampering_is_detected(tmp_path: Path) -> None:
    script = _load_module(PREPARE_SCRIPT, "prepare_candidate_fixture")
    trusted_repo, trusted_project, candidate_project, commit = _make_approved_fixture(tmp_path)
    stage = tmp_path / "verified-stage"
    evidence = tmp_path / "verified-evidence"
    args = SimpleNamespace(
        candidate_sha=commit,
        trusted_root=str(trusted_project),
        trusted_repo_root=str(trusted_repo),
        candidate_root=str(candidate_project),
        stage=str(stage),
        evidence=str(evidence),
        github_output=None,
    )
    assert script.prepare(args) == 0
    manifest = json.loads((evidence / "candidate-manifest.json").read_text(encoding="utf-8"))
    assert manifest["candidateCommit"] == commit
    assert script.verify_manifest(stage, manifest["files"])
    source_file = candidate_project / "tests" / "test_control.py"
    source_file.write_text("changed after staging\n", encoding="utf-8")
    assert script.verify_manifest(stage, manifest["files"])
    assert not script.verify_manifest(candidate_project, manifest["files"])
    staged_file = stage / "tests" / "test_control.py"
    staged_file.chmod(0o644)
    staged_file.write_text("tampered after staging\n", encoding="utf-8")
    assert not script.verify_manifest(stage, manifest["files"])
    _make_writable(stage)


def test_at024_consolidated_register_has_exact_ten_pending_instruction_approvals() -> None:
    inventory = json.loads((PROJECT_ROOT / ".harness" / "instruction-files.json").read_text(encoding="utf-8"))
    register = json.loads(
        (PROJECT_ROOT / ".harness" / "trust" / "approval-register.json").read_text(encoding="utf-8")
    )
    baseline = json.loads(
        (PROJECT_ROOT / ".harness" / "trust" / "bootstrap-baseline.json").read_text(encoding="utf-8")
    )
    assert register["status"] == "PENDING_HUMAN_REVIEW"
    assert register["instruction_files"] == inventory
    assert len(register["instruction_files"]) == 10
    assert register["baseline_sha256"] == _sha256(
        PROJECT_ROOT / ".harness" / "trust" / "bootstrap-baseline.json"
    )
    assert baseline["status"] == "BOOTSTRAP_PENDING_HUMAN_REVIEW"
    baseline_files = {entry["path"]: entry["sha256"] for entry in baseline["files"]}
    prepare_module = _load_module(PREPARE_SCRIPT, "prepare_candidate_inventory")
    assert set(baseline_files) == prepare_module._scoped_files(PROJECT_ROOT)
    assert {entry["path"] for entry in inventory} <= set(baseline_files)
    for relative, digest in baseline_files.items():
        assert digest == _sha256(PROJECT_ROOT / relative)
    trusted_files = {entry["path"]: entry["sha256"] for entry in baseline["trusted_files"]}
    assert set(trusted_files) == {
        ".github/workflows/part-1a-candidate-validation.yml",
        "Part-1A/.harness/trust/prepare_candidate.py",
        "Part-1A/.harness/trust/run_validation.py",
        "Part-1A/.harness/trust/seal_evidence.py",
    }
    for relative, digest in trusted_files.items():
        assert digest == _sha256(REPOSITORY_ROOT / relative)
    assert all(not entry["approval_reference"] for entry in inventory)
    assert all(not value for value in register["approval"].values())
    for entry in register["instruction_files"]:
        assert entry["sha256"] == _sha256(PROJECT_ROOT / entry["path"])


def test_supplemental_evidence_manifest_detects_bundle_tampering(tmp_path: Path) -> None:
    module = _load_module(SEAL_SCRIPT, "seal_evidence_test")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "results.json").write_text('{"status":"PASS"}\n', encoding="utf-8")
    manifest = module.build_evidence_manifest(evidence, "candidate-digest")
    assert module.verify_evidence_manifest(evidence, manifest)
    (evidence / "results.json").write_text('{"status":"FAIL"}\n', encoding="utf-8")
    assert not module.verify_evidence_manifest(evidence, manifest)
