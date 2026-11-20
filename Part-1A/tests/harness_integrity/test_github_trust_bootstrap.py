from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = PROJECT_ROOT.parent
CONTROL_ROOT = Path(os.environ.get("PART1A_REPOSITORY_ROOT", REPOSITORY_ROOT))
WORKFLOW = CONTROL_ROOT / ".github" / "workflows" / "part-1a-candidate-validation.yml"
PREPARE_SCRIPT = PROJECT_ROOT / ".harness" / "trust" / "prepare_candidate.py"
RUN_VALIDATION_SCRIPT = PROJECT_ROOT / ".harness" / "trust" / "run_validation.py"
SEAL_SCRIPT = PROJECT_ROOT / ".harness" / "trust" / "seal_evidence.py"

GOVERNING_SPEC_PATHS = (
    "specs/001-smart-todo-api/checklists/requirements.md",
    "specs/001-smart-todo-api/contracts/openapi.yaml",
    "specs/001-smart-todo-api/data-model.md",
    "specs/001-smart-todo-api/plan.md",
    "specs/001-smart-todo-api/quickstart.md",
    "specs/001-smart-todo-api/research.md",
    "specs/001-smart-todo-api/spec.md",
    "specs/001-smart-todo-api/tasks.md",
    "specs/001-smart-todo-api/test-strategy.md",
)


def _load_module(path: Path, name: str) -> Any:
    sys.path.insert(0, str(PREPARE_SCRIPT.parent))
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


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
    for spec_rel in GOVERNING_SPEC_PATHS:
        _write(trusted_project / spec_rel, f"Approved governing specification {spec_rel}\n")
        inventory.append(
            {
                "path": spec_rel,
                "purpose": f"Synthetic governing specification {spec_rel}",
                "classification": "governing-specification",
                "sha256": _sha256(trusted_project / spec_rel),
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
    assert "pull_request:" in workflow
    assert "branches:\n      - main" in workflow
    assert "workflow_dispatch:" in workflow
    assert "candidate_sha:" in workflow
    assert 'if [[ "$GITHUB_REF_VAL" != "refs/heads/main" ]]; then' in workflow
    assert 'echo "Dispatch this workflow from protected main." >&2' in workflow
    assert "permissions:\n  contents: read" in workflow
    assert workflow.count("uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683") == 2
    assert "uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065" in workflow
    assert "uses: astral-sh/setup-uv@68559e99cc807c1eb7e9238fd43a15bba460eec2" in workflow
    assert "uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02" in workflow
    for line in workflow.splitlines():
        stripped = line.strip()
        if stripped.startswith(("uses:", "- uses:")):
            target = stripped.split("uses:", 1)[1].split("#", 1)[0].strip()
            _, ref = target.split("@", 1)
            assert len(ref) == 40 and all(ch in "0123456789abcdef" for ch in ref), target
    assert "path: trusted" in workflow
    assert "path: candidate" in workflow
    assert "ref: ${{ steps.refs.outputs.trusted_sha }}" in workflow
    assert "ref: ${{ steps.refs.outputs.candidate_sha }}" in workflow
    assert workflow.count("persist-credentials: false") == 2
    assert "enable-cache: false" in workflow
    assert "secrets." not in workflow
    assert "prepare_candidate.py" in workflow
    assert "run_validation.py" in workflow
    assert "Seal and verify evidence bundle" in workflow
    assert "--candidate-root candidate/Part-1A" in workflow


def test_at022_candidate_process_receives_only_allowlisted_environment(tmp_path: Path) -> None:
    module = _load_module(RUN_VALIDATION_SCRIPT, "run_validation_environment_test")
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
    assert environment["UV_OFFLINE"] == "1"
    assert environment["PIP_NO_INDEX"] == "1"
    assert environment["HTTP_PROXY"] == "http://127.0.0.1:9"
    assert environment["HTTPS_PROXY"] == "http://127.0.0.1:9"
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
        "specs/001-smart-todo-api/spec.md",
        "specs/001-smart-todo-api/contracts/openapi.yaml",
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

    # Deleting a governing specification file must block before staging
    spec_file = candidate_project / "specs" / "001-smart-todo-api" / "spec.md"
    spec_bytes = spec_file.read_bytes()
    spec_file.unlink()
    args = SimpleNamespace(
        candidate_sha=commit,
        trusted_root=str(trusted_project),
        trusted_repo_root=str(trusted_repo),
        candidate_root=str(candidate_project),
        stage=str(tmp_path / "deleted-spec-stage"),
        evidence=str(tmp_path / "deleted-spec-evidence"),
        github_output=None,
    )
    assert script.prepare(args) == 2
    spec_file.write_bytes(spec_bytes)

    # Adding an unexpected unlisted specification file under specs/ must block before staging
    extra_spec = candidate_project / "specs" / "001-smart-todo-api" / "unapproved-amendment.md"
    extra_spec.write_text("unapproved spec addition\n", encoding="utf-8")
    args.stage = str(tmp_path / "extra-spec-stage")
    args.evidence = str(tmp_path / "extra-spec-evidence")
    assert script.prepare(args) == 2
    report = json.loads((Path(args.evidence) / "bootstrap-preflight.json").read_text(encoding="utf-8"))
    assert "Unlisted governing specification file" in report["reason"]
    extra_spec.unlink()

    # Wildcard in instruction inventory must block before staging
    inv_path = candidate_project / ".harness" / "instruction-files.json"
    orig_inv = inv_path.read_text(encoding="utf-8")
    inv_data = json.loads(orig_inv)
    inv_data[0]["path"] = "specs/001-smart-todo-api/*.md"
    _write_json(inv_path, inv_data)
    args.stage = str(tmp_path / "wildcard-stage")
    args.evidence = str(tmp_path / "wildcard-evidence")
    assert script.prepare(args) == 2
    report = json.loads((Path(args.evidence) / "bootstrap-preflight.json").read_text(encoding="utf-8"))
    assert "wildcard" in report["reason"].lower()
    inv_path.write_text(orig_inv, encoding="utf-8")


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
    orig_register = json.loads(register_path.read_text(encoding="utf-8"))
    register["instruction_files"][-1]["approval_reference"] = "wrong-reference"
    _write_json(register_path, register)
    args.stage = str(tmp_path / "bad-ref-stage")
    args.evidence = str(tmp_path / "bad-ref-evidence")
    assert script.prepare(args) == 2
    report = json.loads(
        (tmp_path / "bad-ref-evidence" / "bootstrap-preflight.json").read_text(encoding="utf-8")
    )
    assert "approval references must match" in report["reason"]

    register = orig_register
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


def test_at024_instruction_inventory_paths_and_digests_are_current() -> None:
    inventory = json.loads((PROJECT_ROOT / ".harness" / "instruction-files.json").read_text(encoding="utf-8"))
    assert len(inventory) == 19
    assert set(GOVERNING_SPEC_PATHS) <= {entry["path"] for entry in inventory}
    for entry in inventory:
        assert set(entry) == {"path", "purpose", "classification", "sha256", "approval_reference"}
        relative = entry["path"]
        assert isinstance(relative, str) and relative and "*" not in relative and "?" not in relative
        assert isinstance(entry["approval_reference"], str)
        assert entry["sha256"] == _sha256(PROJECT_ROOT / relative)


def test_supplemental_evidence_manifest_detects_bundle_tampering(tmp_path: Path) -> None:
    module = _load_module(SEAL_SCRIPT, "seal_evidence_test")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "results.json").write_text('{"status":"PASS"}\n', encoding="utf-8")
    manifest = module.build_evidence_manifest(evidence, "a" * 64)
    assert module.verify_evidence_manifest(evidence, manifest)
    (evidence / "results.json").write_text('{"status":"FAIL"}\n', encoding="utf-8")
    assert not module.verify_evidence_manifest(evidence, manifest)


def test_ht002_manifest_separation_security_review_and_publication_gate(tmp_path: Path) -> None:
    prepare_module = _load_module(PREPARE_SCRIPT, "prepare_candidate_ht002")
    seal_module = _load_module(SEAL_SCRIPT, "seal_evidence_ht002")
    _, _, candidate_project, _ = _make_approved_fixture(tmp_path)

    initial_entries = prepare_module.build_manifest(candidate_project)
    candidate_digest = prepare_module.manifest_digest(initial_entries)
    candidate_commit = "a" * 40

    # Evidence, runtime data, and caches inside candidate root must not alter candidate digest
    _write(candidate_project / "evidence" / "run-1" / "results.json", '{"status":"PASS"}\n')
    _write(candidate_project / "data" / "tasks.json", '{"next_id":1,"tasks":[]}\n')
    _write(candidate_project / ".pytest_cache" / "state", "cached\n")
    assert prepare_module.manifest_digest(prepare_module.build_manifest(candidate_project)) == candidate_digest

    evidence_root = tmp_path / "detached-evidence"
    _write_json(
        evidence_root / "candidate-manifest.json",
        {
            "schemaVersion": 1,
            "candidateCommit": candidate_commit,
            "manifestDigest": candidate_digest,
            "files": initial_entries,
        },
    )
    _write_json(
        evidence_root / "results.json",
        {
            "schemaVersion": 1,
            "validationMode": "protected-main-candidate-validation",
            "authoritative": False,
            "status": "PASS_AUTOMATED_CHECKS_ONLY",
            "humanSecurityReview": None,
            "humanDecision": None,
            "publicationPermitted": False,
            "candidateCommit": candidate_commit,
            "candidateDigest": candidate_digest,
            "postExecutionIntegrityMatches": True,
            "publicationCandidateMatchesStagedSnapshot": True,
            "gates": [
                {"name": "pytest", "exitCode": 0},
                {"name": "traceability", "exitCode": 0},
                {"name": "ruff", "exitCode": 0},
                {"name": "bandit", "exitCode": 0, "machineReadableFindings": "bandit.json"},
                {"name": "repository-hygiene", "exitCode": 0, "report": "gates/repository-hygiene/hygiene.json"},
            ],
        },
    )
    _write_json(evidence_root / "gates" / "bandit.json", {"results": []})
    bandit_sha = _sha256(evidence_root / "gates" / "bandit.json")
    _write_json(
        evidence_root / "gates" / "repository-hygiene" / "hygiene.json",
        {"findingCount": 0, "syntheticFixtureChecksPassed": True, "secretsOmitted": True},
    )

    # Missing human records must block publication
    initial_bundle_manifest = seal_module.build_evidence_manifest(evidence_root, candidate_digest)
    try:
        seal_module.verify_publication_gate(
            evidence_root=evidence_root,
            final_manifest=initial_bundle_manifest,
            publication_candidate_digest=candidate_digest,
        )
    except ValueError as exc:
        assert "Human security review record" in str(exc)
    else:
        raise AssertionError("Publication gate must block when human security review is missing")

    # Add human security review record and reconstruct pre-decision manifest from disk
    _write_json(
        evidence_root / "security-review" / "review.json",
        {
            "schemaVersion": 1,
            "candidateCommit": candidate_commit,
            "candidateDigest": candidate_digest,
            "banditReportSha256": bandit_sha,
            "reviewer": "Synthetic Reviewer",
            "reviewedAt": "2026-11-13T12:00:00Z",
            "reviewedScope": "Part-1A synthetic candidate",
            "hygieneFindingCount": 0,
            "hygieneDisposition": "Zero hygiene findings verified",
            "banditFindings": [],
            "gateSatisfied": True,
        },
    )
    pre_decision_manifest = seal_module.build_pre_decision_evidence_manifest(evidence_root, candidate_digest)

    # REJECT decision must block publication
    _write_json(
        evidence_root / "human-decision" / "decision.json",
        {
            "schemaVersion": 1,
            "decision": "REJECT",
            "reviewer": "Synthetic Reviewer",
            "decidedAt": "2026-11-13T12:05:00Z",
            "rationale": "Synthetic rejection check",
            "candidateCommit": candidate_commit,
            "candidateDigest": candidate_digest,
            "preDecisionEvidenceBundleDigest": pre_decision_manifest["bundleDigest"],
        },
    )
    reject_manifest = seal_module.build_evidence_manifest(evidence_root, candidate_digest)
    try:
        seal_module.verify_publication_gate(
            evidence_root=evidence_root,
            final_manifest=reject_manifest,
            publication_candidate_digest=candidate_digest,
        )
    except ValueError as exc:
        assert "REJECT" in str(exc)
    else:
        raise AssertionError("Publication gate must block on REJECT")

    # ACCEPT decision referencing pre-decision manifest and sealed into final manifest opens gate
    _write_json(
        evidence_root / "human-decision" / "decision.json",
        {
            "schemaVersion": 1,
            "decision": "ACCEPT",
            "reviewer": "Synthetic Reviewer",
            "decidedAt": "2026-11-13T12:10:00Z",
            "rationale": "Synthetic acceptance check",
            "candidateCommit": candidate_commit,
            "candidateDigest": candidate_digest,
            "preDecisionEvidenceBundleDigest": pre_decision_manifest["bundleDigest"],
        },
    )
    final_manifest = seal_module.build_evidence_manifest(evidence_root, candidate_digest)
    assert seal_module.verify_publication_gate(
        evidence_root=evidence_root,
        final_manifest=final_manifest,
        publication_candidate_digest=candidate_digest,
    )

    # Candidate drift after validation must block publication without changing historical evidence
    _write(candidate_project / "tests" / "test_control.py", "def test_drifted():\n    assert True\n")
    drifted_digest = prepare_module.manifest_digest(prepare_module.build_manifest(candidate_project))
    assert drifted_digest != candidate_digest
    try:
        seal_module.verify_publication_gate(
            evidence_root=evidence_root,
            final_manifest=final_manifest,
            publication_candidate_digest=drifted_digest,
        )
    except ValueError as exc:
        assert "differs from the validated candidate digest" in str(exc)
    else:
        raise AssertionError("Publication gate must block when publication candidate drifts")
