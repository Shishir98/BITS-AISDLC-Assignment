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
SEAL_SCRIPT = TRUST_DIR / "seal_evidence.py"


def _load_seal_module() -> Any:
    sys.path.insert(0, str(TRUST_DIR))
    try:
        spec = importlib.util.spec_from_file_location("seal_evidence_security_gate", SEAL_SCRIPT)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


def _sample_bandit_report() -> tuple[dict[str, Any], str]:
    report = {
        "results": [
            {
                "test_id": "B101",
                "test_name": "assert_used",
                "filename": "src/smart_todo/domain/service.py",
                "line_number": 42,
                "col_offset": 8,
                "issue_severity": "LOW",
                "issue_confidence": "HIGH",
                "issue_text": "Use of assert detected. The enclosed code will be removed when compiling to optimised byte code.",
            },
            {
                "test_id": "B311",
                "test_name": "blacklist",
                "filename": "src\\smart_todo\\persistence\\json_repository.py",
                "line_number": 108,
                "col_offset": 12,
                "issue_severity": "LOW",
                "issue_confidence": "HIGH",
                "issue_text": "Standard pseudo-random generators are not suitable for security/cryptographic purposes.",
            },
        ]
    }
    raw = (json.dumps(report, indent=2) + "\n").encode("utf-8")
    return report, hashlib.sha256(raw).hexdigest()


def test_at027_security_review_verifies_exact_bandit_finding_identities_and_dispositions() -> None:
    seal = _load_seal_module()
    bandit_report, bandit_sha = _sample_bandit_report()
    hygiene_report = {"findingCount": 0, "syntheticFixtureChecksPassed": True, "secretsOmitted": True}
    candidate_digest = "a" * 64
    candidate_commit = "b" * 40

    expected_ids = seal.derive_bandit_finding_ids(bandit_report)
    assert len(expected_ids) == 2
    assert expected_ids[0].startswith("B101:src/smart_todo/domain/service.py:42:")
    assert expected_ids[1].startswith("B311:src/smart_todo/persistence/json_repository.py:108:")

    valid_record = {
        "schemaVersion": 1,
        "candidateCommit": candidate_commit,
        "candidateDigest": candidate_digest,
        "banditReportSha256": bandit_sha,
        "reviewer": "Human Security Reviewer",
        "reviewedAt": "2026-11-14T00:00:00Z",
        "reviewedScope": "Part-1A full repository and src/smart_todo",
        "hygieneFindingCount": 0,
        "hygieneDisposition": "Zero repository-hygiene findings verified across tracked and candidate trees.",
        "banditFindings": [
            {
                "findingId": expected_ids[0],
                "disposition": "ACCEPTED_FALSE_POSITIVE",
                "rationale": "Internal invariant check only; not used for authentication or input validation.",
            },
            {
                "findingId": expected_ids[1],
                "disposition": "DOCUMENTED_DISPOSITION",
                "rationale": "Used only for non-cryptographic temp filename suffix generation.",
            },
        ],
        "gateSatisfied": True,
    }

    seal.verify_security_review_record(
        valid_record,
        expected_candidate_digest=candidate_digest,
        bandit_report=bandit_report,
        hygiene_report=hygiene_report,
        expected_bandit_report_sha256=bandit_sha,
        expected_candidate_commit=candidate_commit,
    )


def test_at027_security_review_rejects_count_only_duplicate_fabricated_missing_and_mismatched_findings() -> None:
    seal = _load_seal_module()
    bandit_report, bandit_sha = _sample_bandit_report()
    hygiene_report = {"findingCount": 0}
    candidate_digest = "a" * 64
    candidate_commit = "b" * 40
    expected_ids = seal.derive_bandit_finding_ids(bandit_report)

    def make_record(findings: list[dict[str, str]], **overrides: Any) -> dict[str, Any]:
        record: dict[str, Any] = {
            "schemaVersion": 1,
            "candidateCommit": candidate_commit,
            "candidateDigest": candidate_digest,
            "banditReportSha256": bandit_sha,
            "reviewer": "Human Security Reviewer",
            "reviewedAt": "2026-11-14T00:00:00Z",
            "reviewedScope": "Part-1A",
            "hygieneFindingCount": 0,
            "hygieneDisposition": "Clean",
            "banditFindings": findings,
            "gateSatisfied": True,
        }
        record.update(overrides)
        return record

    # 1. Count-only match with wrong/fabricated findingId must be rejected
    with pytest.raises(ValueError, match="unknown or fabricated Bandit findingId"):
        seal.verify_security_review_record(
            make_record(
                [
                    {"findingId": expected_ids[0], "disposition": "RESOLVED", "rationale": "Fixed"},
                    {"findingId": "B999:src/fake.py:1:0123456789abcdef", "disposition": "RESOLVED", "rationale": "Fake"},
                ]
            ),
            expected_candidate_digest=candidate_digest,
            bandit_report=bandit_report,
            hygiene_report=hygiene_report,
            expected_bandit_report_sha256=bandit_sha,
            expected_candidate_commit=candidate_commit,
        )

    # 2. Duplicate findingId with same count must be rejected
    with pytest.raises(ValueError, match="duplicate Bandit findingId"):
        seal.verify_security_review_record(
            make_record(
                [
                    {"findingId": expected_ids[0], "disposition": "RESOLVED", "rationale": "First"},
                    {"findingId": expected_ids[0], "disposition": "RESOLVED", "rationale": "Duplicate"},
                ]
            ),
            expected_candidate_digest=candidate_digest,
            bandit_report=bandit_report,
            hygiene_report=hygiene_report,
            expected_bandit_report_sha256=bandit_sha,
            expected_candidate_commit=candidate_commit,
        )

    # 3. Missing findingId must be rejected
    with pytest.raises(ValueError, match="missing required Bandit findingId"):
        seal.verify_security_review_record(
            make_record(
                [
                    {"findingId": expected_ids[0], "disposition": "RESOLVED", "rationale": "Only one"},
                ]
            ),
            expected_candidate_digest=candidate_digest,
            bandit_report=bandit_report,
            hygiene_report=hygiene_report,
            expected_bandit_report_sha256=bandit_sha,
            expected_candidate_commit=candidate_commit,
        )

    # 4. Out-of-order findingIds must be rejected
    with pytest.raises(ValueError, match="order does not match"):
        seal.verify_security_review_record(
            make_record(
                [
                    {"findingId": expected_ids[1], "disposition": "RESOLVED", "rationale": "Second first"},
                    {"findingId": expected_ids[0], "disposition": "RESOLVED", "rationale": "First second"},
                ]
            ),
            expected_candidate_digest=candidate_digest,
            bandit_report=bandit_report,
            hygiene_report=hygiene_report,
            expected_bandit_report_sha256=bandit_sha,
            expected_candidate_commit=candidate_commit,
        )

    # 5. Mismatched Bandit report SHA-256 must be rejected
    with pytest.raises(ValueError, match="banditReportSha256 does not match"):
        seal.verify_security_review_record(
            make_record(
                [
                    {"findingId": expected_ids[0], "disposition": "RESOLVED", "rationale": "Ok"},
                    {"findingId": expected_ids[1], "disposition": "RESOLVED", "rationale": "Ok"},
                ],
                banditReportSha256="c" * 64,
            ),
            expected_candidate_digest=candidate_digest,
            bandit_report=bandit_report,
            hygiene_report=hygiene_report,
            expected_bandit_report_sha256=bandit_sha,
            expected_candidate_commit=candidate_commit,
        )
