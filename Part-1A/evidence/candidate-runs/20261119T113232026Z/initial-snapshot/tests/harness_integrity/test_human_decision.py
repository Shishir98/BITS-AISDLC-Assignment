from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TRUST_DIR = PROJECT_ROOT / ".harness" / "trust"
PREPARE_SCRIPT = TRUST_DIR / "prepare_candidate.py"
SEAL_SCRIPT = TRUST_DIR / "seal_evidence.py"


def _load_modules() -> tuple[Any, Any]:
    sys.path.insert(0, str(TRUST_DIR))
    try:
        prep_spec = importlib.util.spec_from_file_location("prepare_candidate_decision_gate", PREPARE_SCRIPT)
        seal_spec = importlib.util.spec_from_file_location("seal_evidence_decision_gate", SEAL_SCRIPT)
        assert prep_spec is not None and prep_spec.loader is not None
        assert seal_spec is not None and seal_spec.loader is not None
        prep_mod = importlib.util.module_from_spec(prep_spec)
        seal_mod = importlib.util.module_from_spec(seal_spec)
        prep_spec.loader.exec_module(prep_mod)
        seal_spec.loader.exec_module(seal_mod)
        return prep_mod, seal_mod
    finally:
        sys.path.pop(0)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _build_pre_decision_fixture(tmp_path: Path) -> tuple[Path, Path, str, str]:
    prep, seal = _load_modules()
    candidate_root = tmp_path / "candidate"
    (candidate_root / "src").mkdir(parents=True)
    (candidate_root / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
    entries = prep.build_manifest(candidate_root)
    candidate_digest = prep.manifest_digest(entries)
    candidate_commit = "d" * 40

    evidence_root = tmp_path / "evidence"
    _write_json(
        evidence_root / "candidate-manifest.json",
        {
            "schemaVersion": 1,
            "candidateCommit": candidate_commit,
            "manifestDigest": candidate_digest,
            "files": entries,
        },
    )
    _write_json(
        evidence_root / "gates" / "bandit.json",
        {
            "results": [
                {
                    "test_id": "B105",
                    "filename": "src/app.py",
                    "line_number": 1,
                    "col_offset": 0,
                    "issue_severity": "LOW",
                    "issue_confidence": "MEDIUM",
                    "issue_text": "Possible hardcoded password.",
                }
            ]
        },
    )
    bandit_sha = hashlib.sha256((evidence_root / "gates" / "bandit.json").read_bytes()).hexdigest()
    finding_ids = seal.derive_bandit_finding_ids(
        json.loads((evidence_root / "gates" / "bandit.json").read_text(encoding="utf-8"))
    )
    (evidence_root / "gates" / "pytest.stdout.txt").write_text("1 passed\n", encoding="utf-8")
    (evidence_root / "gates" / "pytest.stderr.txt").write_text("", encoding="utf-8")
    _write_json(
        evidence_root / "gates" / "repository-hygiene" / "hygiene.json",
        {"findingCount": 0, "syntheticFixtureChecksPassed": True, "secretsOmitted": True},
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
                {
                    "name": "pytest",
                    "exitCode": 0,
                    "stdout": "pytest.stdout.txt",
                    "stderr": "pytest.stderr.txt",
                },
                {
                    "name": "bandit",
                    "exitCode": 0,
                    "machineReadableFindings": "bandit.json",
                },
                {
                    "name": "repository-hygiene",
                    "exitCode": 0,
                    "report": "gates/repository-hygiene/hygiene.json",
                },
            ],
        },
    )
    _write_json(
        evidence_root / "security-review" / "review.json",
        {
            "schemaVersion": 1,
            "candidateCommit": candidate_commit,
            "candidateDigest": candidate_digest,
            "banditReportSha256": bandit_sha,
            "reviewer": "Human Security Reviewer",
            "reviewedAt": "2026-11-14T00:10:00Z",
            "reviewedScope": "Part-1A",
            "hygieneFindingCount": 0,
            "hygieneDisposition": "Zero hygiene findings verified.",
            "banditFindings": [
                {
                    "findingId": finding_ids[0],
                    "disposition": "ACCEPTED_FALSE_POSITIVE",
                    "rationale": "Constant is not a password.",
                }
            ],
            "gateSatisfied": True,
        },
    )
    return candidate_root, evidence_root, candidate_digest, candidate_commit


def test_at028_human_decision_gate_reconstructs_pre_decision_digest_and_verifies_acceptance(
    tmp_path: Path,
) -> None:
    _, seal = _load_modules()
    candidate_root, evidence_root, candidate_digest, candidate_commit = _build_pre_decision_fixture(tmp_path)

    reconstructed_pre = seal.build_pre_decision_evidence_manifest(evidence_root, candidate_digest)
    _write_json(
        evidence_root / "human-decision" / "decision.json",
        {
            "schemaVersion": 1,
            "decision": "ACCEPT",
            "reviewer": "Human Final Reviewer",
            "decidedAt": "2026-11-14T00:15:00Z",
            "rationale": "All gates and security reviews verified.",
            "candidateCommit": candidate_commit,
            "candidateDigest": candidate_digest,
            "preDecisionEvidenceBundleDigest": reconstructed_pre["bundleDigest"],
        },
    )
    manifest_path = tmp_path / "final-evidence-manifest.json"
    assert seal.seal(
        evidence_root,
        manifest_path,
        candidate_root=candidate_root,
        candidate_sha=candidate_commit,
        verify_publication=True,
    )
    final_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert final_manifest["bundleDigest"] != reconstructed_pre["bundleDigest"]
    assert seal.verify_publication_gate(
        evidence_root=evidence_root,
        final_manifest=final_manifest,
        publication_candidate_digest=candidate_digest,
        expected_candidate_commit=candidate_commit,
    )


def test_at028_human_decision_gate_rejects_pre_decision_tampering_missing_or_unexpected_files_and_reject_decisions(
    tmp_path: Path,
) -> None:
    _, seal = _load_modules()
    _, evidence_root, candidate_digest, candidate_commit = _build_pre_decision_fixture(tmp_path)
    pre_manifest = seal.build_pre_decision_evidence_manifest(evidence_root, candidate_digest)

    # 1. REJECT decision must block publication
    _write_json(
        evidence_root / "human-decision" / "decision.json",
        {
            "schemaVersion": 1,
            "decision": "REJECT",
            "reviewer": "Human Final Reviewer",
            "decidedAt": "2026-11-14T00:15:00Z",
            "rationale": "Rejected for test.",
            "candidateCommit": candidate_commit,
            "candidateDigest": candidate_digest,
            "preDecisionEvidenceBundleDigest": pre_manifest["bundleDigest"],
        },
    )
    reject_manifest = seal.build_evidence_manifest(evidence_root, candidate_digest)
    with pytest.raises(ValueError, match="REJECT"):
        seal.verify_publication_gate(
            evidence_root=evidence_root,
            final_manifest=reject_manifest,
            publication_candidate_digest=candidate_digest,
            expected_candidate_commit=candidate_commit,
        )

    # Write valid ACCEPT decision
    _write_json(
        evidence_root / "human-decision" / "decision.json",
        {
            "schemaVersion": 1,
            "decision": "ACCEPT",
            "reviewer": "Human Final Reviewer",
            "decidedAt": "2026-11-14T00:16:00Z",
            "rationale": "Accepted.",
            "candidateCommit": candidate_commit,
            "candidateDigest": candidate_digest,
            "preDecisionEvidenceBundleDigest": pre_manifest["bundleDigest"],
        },
    )

    # 2. Tamper with a pre-decision file AND reseal final_manifest: must still fail because
    # verify_publication_gate independently reconstructs preDecisionEvidenceBundleDigest from disk!
    pytest_stdout = evidence_root / "gates" / "pytest.stdout.txt"
    original_stdout = pytest_stdout.read_text(encoding="utf-8")
    pytest_stdout.write_text("tampered after decision\n", encoding="utf-8")
    resealed_tampered_manifest = seal.build_evidence_manifest(evidence_root, candidate_digest)
    with pytest.raises(
        ValueError,
        match="preDecisionEvidenceBundleDigest does not match the independently reconstructed pre-decision evidence bundle",
    ):
        seal.verify_publication_gate(
            evidence_root=evidence_root,
            final_manifest=resealed_tampered_manifest,
            publication_candidate_digest=candidate_digest,
            expected_candidate_commit=candidate_commit,
        )
    pytest_stdout.write_text(original_stdout, encoding="utf-8")

    # 3. Unexpected file in evidence bundle must be rejected
    unexpected_file = evidence_root / "unexpected-artifact.txt"
    unexpected_file.write_text("rogue file\n", encoding="utf-8")
    unexpected_manifest = seal.build_evidence_manifest(evidence_root, candidate_digest)
    with pytest.raises(ValueError, match="Unexpected file in evidence bundle"):
        seal.verify_publication_gate(
            evidence_root=evidence_root,
            final_manifest=unexpected_manifest,
            publication_candidate_digest=candidate_digest,
            expected_candidate_commit=candidate_commit,
        )
    unexpected_file.unlink()

    # 4. Missing referenced gate file must be rejected
    pytest_stdout.unlink()
    missing_gate_manifest = seal.build_evidence_manifest(evidence_root, candidate_digest)
    with pytest.raises(ValueError, match="Gate output file referenced in results.json is missing"):
        seal.verify_publication_gate(
            evidence_root=evidence_root,
            final_manifest=missing_gate_manifest,
            publication_candidate_digest=candidate_digest,
            expected_candidate_commit=candidate_commit,
        )
    pytest_stdout.write_text(original_stdout, encoding="utf-8")

    # 5. Path traversal and duplicate path in manifest structure must be rejected
    valid_manifest = seal.build_evidence_manifest(evidence_root, candidate_digest)
    traversal_manifest = dict(valid_manifest)
    traversal_manifest["files"] = [{"path": "../escape.json", "sha256": "a" * 64}]
    with pytest.raises(ValueError, match="path traversal"):
        seal.verify_evidence_manifest(evidence_root, traversal_manifest)

    dup_manifest = dict(valid_manifest)
    dup_manifest["files"] = [
        {"path": "results.json", "sha256": "a" * 64},
        {"path": "RESULTS.json", "sha256": "a" * 64},
    ]
    with pytest.raises(ValueError, match="duplicate path"):
        seal.verify_evidence_manifest(evidence_root, dup_manifest)
