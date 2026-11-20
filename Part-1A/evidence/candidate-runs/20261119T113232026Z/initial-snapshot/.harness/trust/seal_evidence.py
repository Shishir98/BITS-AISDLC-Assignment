from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from prepare_candidate import build_manifest, manifest_digest

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

ALLOWED_TOP_LEVEL_EVIDENCE_FILES = {
    "bootstrap-preflight.json",
    "candidate-manifest.json",
    "dispatch.txt",
    "junit.xml",
    "post-execution-integrity.txt",
    "pre-execution-integrity.txt",
    "results.json",
    "traceability.json",
}
REQUIRED_PRE_DECISION_FILES = (
    "candidate-manifest.json",
    "results.json",
    "gates/bandit.json",
    "gates/repository-hygiene/hygiene.json",
    "security-review/review.json",
)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _validate_iso_timestamp(value: Any, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty ISO-8601 timestamp string.")
    normalized = f"{value[:-1]}+00:00" if value.endswith("Z") else value
    try:
        datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{label} is not a valid ISO-8601 timestamp.") from exc


def _validate_evidence_relative_path(relative: Any) -> str:
    if not isinstance(relative, str) or not relative.strip():
        raise ValueError("Evidence manifest path must be a non-empty string.")
    if "\\" in relative or relative.startswith("/") or "*" in relative or "?" in relative:
        raise ValueError(f"Evidence manifest contains an unsafe path: {relative}")
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"Evidence manifest contains path traversal or absolute path: {relative}")
    return relative


def _validate_manifest_structure(manifest: dict[str, Any]) -> None:
    if not isinstance(manifest, dict) or set(manifest.keys()) != {
        "schemaVersion",
        "candidateDigest",
        "bundleDigest",
        "files",
    }:
        raise ValueError("Evidence manifest does not contain the exact required top-level fields.")
    if manifest.get("schemaVersion") != 1:
        raise ValueError("Evidence manifest schemaVersion must be 1.")
    bundle_digest = manifest.get("bundleDigest")
    if not isinstance(bundle_digest, str) or not _SHA256_RE.fullmatch(bundle_digest):
        raise ValueError("Evidence manifest bundleDigest must be a 64-character lowercase SHA-256.")
    files = manifest.get("files")
    if not isinstance(files, list):
        raise TypeError("Evidence manifest files must be a list.")
    seen_lower: set[str] = set()
    ordered_paths: list[str] = []
    for entry in files:
        if not isinstance(entry, dict) or set(entry.keys()) != {"path", "sha256"}:
            raise ValueError("Evidence manifest file entry must contain exact keys 'path' and 'sha256'.")
        rel = _validate_evidence_relative_path(entry.get("path"))
        digest = entry.get("sha256")
        if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
            raise ValueError(f"Evidence manifest file entry has invalid sha256 for {rel}.")
        norm = rel.lower()
        if norm in seen_lower:
            raise ValueError(f"Evidence manifest contains duplicate path: {rel}")
        seen_lower.add(norm)
        ordered_paths.append(rel)
    if ordered_paths != sorted(ordered_paths):
        raise ValueError("Evidence manifest files are not in canonical sorted order.")
    canonical = "\n".join(f'{entry["path"]}  {entry["sha256"]}' for entry in files)
    if _sha256_bytes(canonical.encode("utf-8")) != bundle_digest:
        raise ValueError("Evidence manifest bundleDigest does not match its file entries.")


def build_evidence_manifest(
    evidence_root: Path,
    candidate_digest: str,
    *,
    exclude_paths: set[str] | None = None,
) -> dict[str, Any]:
    excluded = exclude_paths or set()
    files: list[dict[str, str]] = []
    seen_lower: set[str] = set()
    for path in evidence_root.rglob("*"):
        relative = path.relative_to(evidence_root).as_posix()
        if relative in excluded:
            continue
        if path.is_symlink():
            raise ValueError(f"Evidence contains a symbolic link: {relative}")
        if path.is_file():
            _validate_evidence_relative_path(relative)
            norm = relative.lower()
            if norm in seen_lower:
                raise ValueError(f"Evidence directory contains duplicate normalized path: {relative}")
            seen_lower.add(norm)
            files.append(
                {
                    "path": relative,
                    "sha256": _sha256_file(path),
                }
            )
    files.sort(key=lambda entry: entry["path"])
    canonical = "\n".join(f'{entry["path"]}  {entry["sha256"]}' for entry in files)
    return {
        "schemaVersion": 1,
        "candidateDigest": candidate_digest,
        "bundleDigest": _sha256_bytes(canonical.encode("utf-8")),
        "files": files,
    }


def verify_evidence_manifest(evidence_root: Path, manifest: dict[str, Any]) -> bool:
    _validate_manifest_structure(manifest)
    return build_evidence_manifest(evidence_root, manifest["candidateDigest"]) == manifest


def derive_bandit_finding_id(finding: dict[str, Any]) -> str:
    if not isinstance(finding, dict):
        raise TypeError("Bandit finding entry must be a JSON object.")
    test_id = finding.get("test_id")
    filename = finding.get("filename")
    line_number = finding.get("line_number")
    col_offset = finding.get("col_offset", 0)
    severity = finding.get("issue_severity")
    confidence = finding.get("issue_confidence")
    issue_text = finding.get("issue_text")
    if not all(isinstance(val, str) and val.strip() for val in (test_id, filename, severity, confidence, issue_text)):
        raise ValueError("Bandit finding is missing required identifying string fields.")
    if isinstance(line_number, bool) or not isinstance(line_number, int) or line_number <= 0:
        raise ValueError("Bandit finding line_number must be a positive integer.")
    if isinstance(col_offset, bool) or not isinstance(col_offset, int) or col_offset < 0:
        raise ValueError("Bandit finding col_offset must be a non-negative integer.")
    norm_file = str(filename).replace("\\", "/").lstrip("./")
    canonical = (
        f"{test_id.strip()}|{norm_file}|{line_number}|{col_offset}|"
        f"{severity.strip().upper()}|{confidence.strip().upper()}|{issue_text.strip()}"
    )
    digest16 = _sha256_bytes(canonical.encode("utf-8"))[:16]
    return f"{test_id.strip()}:{norm_file}:{line_number}:{digest16}"


def derive_bandit_finding_ids(bandit_report: dict[str, Any]) -> list[str]:
    if not isinstance(bandit_report, dict):
        raise TypeError("Bandit report must be a JSON object.")
    raw_findings = bandit_report.get("results")
    if not isinstance(raw_findings, list):
        raise TypeError("Bandit report does not contain a findings list.")
    finding_ids = [derive_bandit_finding_id(item) for item in raw_findings]
    if len(set(finding_ids)) != len(finding_ids):
        raise ValueError("Bandit report contains duplicate non-unique finding identities.")
    return finding_ids


def verify_security_review_record(
    record: dict[str, Any],
    *,
    expected_candidate_digest: str,
    bandit_report: dict[str, Any],
    hygiene_report: dict[str, Any],
    expected_bandit_report_sha256: str | None = None,
    expected_candidate_commit: str | None = None,
) -> None:
    if not isinstance(record, dict):
        raise TypeError("Security review record must be a JSON object.")
    required_keys = {
        "schemaVersion",
        "candidateDigest",
        "banditReportSha256",
        "reviewer",
        "reviewedAt",
        "reviewedScope",
        "hygieneFindingCount",
        "hygieneDisposition",
        "banditFindings",
        "gateSatisfied",
    }
    optional_keys = {"candidateCommit"}
    actual_keys = set(record.keys())
    if not required_keys.issubset(actual_keys) or not actual_keys.issubset(required_keys | optional_keys):
        raise ValueError("Security review record does not contain the exact required fields.")
    if record.get("schemaVersion") != 1:
        raise ValueError("Security review record schemaVersion must be 1.")
    if not _SHA256_RE.fullmatch(str(record.get("candidateDigest", ""))):
        raise ValueError("Security review record candidateDigest must be a 64-character lowercase SHA-256.")
    if record["candidateDigest"] != expected_candidate_digest:
        raise ValueError("Security review record candidateDigest does not match the validated candidate.")
    if expected_candidate_commit is not None or "candidateCommit" in record:
        commit_val = str(record.get("candidateCommit", ""))
        if not _COMMIT_SHA_RE.fullmatch(commit_val):
            raise ValueError("Security review record candidateCommit must be a 40-character lowercase SHA.")
        if expected_candidate_commit is not None and commit_val != expected_candidate_commit:
            raise ValueError("Security review record candidateCommit does not match the validated candidate commit.")

    bandit_sha = str(record.get("banditReportSha256", ""))
    if not _SHA256_RE.fullmatch(bandit_sha):
        raise ValueError("Security review record banditReportSha256 must be a 64-character lowercase SHA-256.")
    if expected_bandit_report_sha256 is not None and bandit_sha != expected_bandit_report_sha256:
        raise ValueError("Security review record banditReportSha256 does not match the Bandit report digest.")

    for text_field in ("reviewer", "reviewedScope", "hygieneDisposition"):
        if not isinstance(record.get(text_field), str) or not record[text_field].strip():
            raise ValueError(f"Security review field '{text_field}' must be a non-empty string.")
    _validate_iso_timestamp(record.get("reviewedAt"), "Security review reviewedAt")
    if hygiene_report.get("findingCount", -1) != 0 or record.get("hygieneFindingCount") != 0:
        raise ValueError("Publication requires zero repository-hygiene findings.")
    if record.get("gateSatisfied") is not True:
        raise ValueError("Human security review gateSatisfied is not true.")

    expected_ids = derive_bandit_finding_ids(bandit_report)
    reviewed_findings = record.get("banditFindings")
    if not isinstance(reviewed_findings, list):
        raise TypeError("Security review banditFindings must be a list.")
    reviewed_ids: list[str] = []
    for item in reviewed_findings:
        if not isinstance(item, dict) or set(item.keys()) != {"findingId", "disposition", "rationale"}:
            raise ValueError("Each Bandit finding review entry requires findingId, disposition, and rationale.")
        if not all(isinstance(item[k], str) and item[k].strip() for k in ("findingId", "disposition", "rationale")):
            raise ValueError("Bandit finding disposition fields must be non-empty strings.")
        if item["disposition"] not in {"RESOLVED", "ACCEPTED_FALSE_POSITIVE", "DOCUMENTED_DISPOSITION"}:
            raise ValueError(f"Unsupported Bandit finding disposition: {item['disposition']}")
        reviewed_ids.append(item["findingId"])

    if len(set(reviewed_ids)) != len(reviewed_ids):
        raise ValueError("Security review record contains duplicate Bandit findingId entries.")
    unknown_ids = sorted(set(reviewed_ids) - set(expected_ids))
    if unknown_ids:
        raise ValueError(f"Security review record contains unknown or fabricated Bandit findingId(s): {unknown_ids}")
    missing_ids = sorted(set(expected_ids) - set(reviewed_ids))
    if missing_ids:
        raise ValueError(f"Security review record is missing required Bandit findingId(s): {missing_ids}")
    if reviewed_ids != expected_ids:
        raise ValueError("Security review record Bandit findingId order does not match the Bandit report.")


def _validate_evidence_file_layout(
    evidence_root: Path,
    *,
    require_security_review: bool,
    allow_human_decision: bool,
) -> set[str]:
    results_path = evidence_root / "results.json"
    if not results_path.is_file():
        raise ValueError("Required evidence file is missing: results.json")
    results = json.loads(results_path.read_text(encoding="utf-8"))
    gates = results.get("gates")
    if not isinstance(gates, list) or not gates:
        raise ValueError("Automated validation results.json does not contain a non-empty gates list.")

    allowed_files = set(ALLOWED_TOP_LEVEL_EVIDENCE_FILES)
    allowed_files.update(
        {
            "gates/bandit.json",
            "gates/repository-hygiene/hygiene.json",
            "gates/repository-hygiene/hygiene.txt",
        }
    )
    if require_security_review:
        allowed_files.add("security-review/review.json")
    if allow_human_decision:
        allowed_files.add("human-decision/decision.json")

    required_gate_files: set[str] = set()
    for gate in gates:
        if not isinstance(gate, dict) or not isinstance(gate.get("name"), str):
            raise TypeError("Malformed gate entry in results.json.")
        gate_name = gate["name"]
        allowed_files.add(f"gates/{gate_name}.stdout.txt")
        allowed_files.add(f"gates/{gate_name}.stderr.txt")
        for ref_key in ("stdout", "stderr", "machineReadableFindings"):
            ref_val = gate.get(ref_key)
            if isinstance(ref_val, str) and ref_val.strip() and ref_val != "unavailable":
                rel_ref = ref_val if ref_val.startswith("gates/") else f"gates/{ref_val}"
                allowed_files.add(rel_ref)
                required_gate_files.add(rel_ref)
        report_val = gate.get("report")
        if isinstance(report_val, str) and report_val.strip():
            allowed_files.add(report_val)
            required_gate_files.add(report_val)

    for req_rel in required_gate_files:
        if not (evidence_root / Path(req_rel)).is_file():
            raise ValueError(f"Gate output file referenced in results.json is missing: {req_rel}")

    if require_security_review:
        for req_file in REQUIRED_PRE_DECISION_FILES:
            if not (evidence_root / Path(req_file)).is_file():
                raise ValueError(f"Required pre-decision evidence file is missing: {req_file}")

    for path in evidence_root.rglob("*"):
        relative = path.relative_to(evidence_root).as_posix()
        if path.is_symlink():
            raise ValueError(f"Evidence contains a symbolic link: {relative}")
        if path.is_file():
            _validate_evidence_relative_path(relative)
            if relative not in allowed_files:
                raise ValueError(f"Unexpected file in evidence bundle: {relative}")

    return allowed_files


def build_pre_decision_evidence_manifest(evidence_root: Path, candidate_digest: str) -> dict[str, Any]:
    if not _SHA256_RE.fullmatch(str(candidate_digest)):
        raise ValueError("Candidate digest must be a 64-character lowercase SHA-256.")
    _validate_evidence_file_layout(
        evidence_root,
        require_security_review=True,
        allow_human_decision=True,
    )
    return build_evidence_manifest(
        evidence_root,
        candidate_digest,
        exclude_paths={"human-decision/decision.json"},
    )


def verify_human_decision_record(
    record: dict[str, Any],
    *,
    expected_candidate_digest: str,
    expected_pre_decision_evidence_digest: str,
    expected_candidate_commit: str | None = None,
) -> None:
    if not isinstance(record, dict):
        raise TypeError("Human decision record must be a JSON object.")
    required_keys = {
        "schemaVersion",
        "decision",
        "reviewer",
        "decidedAt",
        "rationale",
        "candidateDigest",
        "preDecisionEvidenceBundleDigest",
    }
    optional_keys = {"candidateCommit"}
    actual_keys = set(record.keys())
    if not required_keys.issubset(actual_keys) or not actual_keys.issubset(required_keys | optional_keys):
        raise ValueError("Human decision record does not contain the exact required fields.")
    if record.get("schemaVersion") != 1:
        raise ValueError("Human decision record schemaVersion must be 1.")
    decision = record.get("decision")
    if decision not in {"ACCEPT", "REJECT"}:
        raise ValueError("Human decision must be explicitly ACCEPT or REJECT.")
    for text_field in ("reviewer", "rationale"):
        if not isinstance(record.get(text_field), str) or not record[text_field].strip():
            raise ValueError(f"Human decision field '{text_field}' must be a non-empty string.")
    _validate_iso_timestamp(record.get("decidedAt"), "Human decision decidedAt")
    if expected_candidate_commit is not None:
        commit_val = str(record.get("candidateCommit", ""))
        if not _COMMIT_SHA_RE.fullmatch(commit_val):
            raise ValueError("Human decision record must include a valid 40-character candidateCommit.")
        if commit_val != expected_candidate_commit:
            raise ValueError("Human decision candidateCommit does not match the validated candidate commit.")
    elif "candidateCommit" in record and not _COMMIT_SHA_RE.fullmatch(str(record.get("candidateCommit", ""))):
        raise ValueError("Human decision candidateCommit must be a 40-character lowercase SHA.")

    if record.get("candidateDigest") != expected_candidate_digest:
        raise ValueError("Human decision candidateDigest does not match the validated candidate.")
    if record.get("preDecisionEvidenceBundleDigest") != expected_pre_decision_evidence_digest:
        raise ValueError(
            "Human decision preDecisionEvidenceBundleDigest does not match the independently reconstructed pre-decision evidence bundle."
        )
    if decision != "ACCEPT":
        raise ValueError("Publication is blocked because the human decision is REJECT.")


def verify_publication_gate(
    *,
    evidence_root: Path,
    final_manifest: dict[str, Any],
    publication_candidate_digest: str,
    expected_candidate_commit: str | None = None,
) -> bool:
    if not verify_evidence_manifest(evidence_root, final_manifest):
        raise ValueError("Final evidence bundle failed manifest verification.")
    candidate_digest = final_manifest.get("candidateDigest", "")
    if not _SHA256_RE.fullmatch(str(candidate_digest)):
        raise ValueError("Evidence manifest does not contain a valid candidate digest.")
    if publication_candidate_digest != candidate_digest:
        raise ValueError("Publication candidate digest differs from the validated candidate digest.")

    candidate_manifest_path = evidence_root / "candidate-manifest.json"
    if not candidate_manifest_path.is_file():
        raise ValueError("Required publication record is missing: candidate-manifest.json")
    candidate_manifest = json.loads(candidate_manifest_path.read_text(encoding="utf-8"))
    if candidate_manifest.get("manifestDigest") != candidate_digest:
        raise ValueError("candidate-manifest.json manifestDigest does not match the evidence manifest.")
    candidate_commit = str(candidate_manifest.get("candidateCommit", ""))
    if not _COMMIT_SHA_RE.fullmatch(candidate_commit):
        raise ValueError("candidate-manifest.json does not contain a valid 40-character candidateCommit.")
    if expected_candidate_commit is not None and candidate_commit != expected_candidate_commit:
        raise ValueError("candidate-manifest.json candidateCommit does not match expected candidate commit.")
    manifest_entries = candidate_manifest.get("files")
    if not isinstance(manifest_entries, list) or manifest_digest(manifest_entries) != candidate_digest:
        raise ValueError("candidate-manifest.json file list does not match its manifestDigest.")

    results_path = evidence_root / "results.json"
    if not results_path.is_file():
        raise ValueError("Automated validation results.json is missing from evidence.")
    results = json.loads(results_path.read_text(encoding="utf-8"))
    if (
        results.get("humanDecision") is not None
        or results.get("humanSecurityReview") is not None
        or results.get("publicationPermitted") is not False
    ):
        raise ValueError("Automated validation results must not contain human review or decision values.")
    if results.get("candidateDigest") != candidate_digest:
        raise ValueError("Automated validation results candidateDigest does not match the evidence manifest.")
    if results.get("candidateCommit") != candidate_commit:
        raise ValueError("Automated validation results candidateCommit does not match candidate-manifest.json.")
    if not results.get("postExecutionIntegrityMatches") or not results.get("publicationCandidateMatchesStagedSnapshot"):
        raise ValueError("Post-execution staging or publication-candidate equality check failed.")
    gates = results.get("gates", [])
    if not gates or any(gate.get("exitCode") != 0 for gate in gates):
        raise ValueError("All automated validation gates must pass before publication.")

    bandit_path = evidence_root / "gates" / "bandit.json"
    hygiene_path = evidence_root / "gates" / "repository-hygiene" / "hygiene.json"
    security_review_path = evidence_root / "security-review" / "review.json"
    decision_path = evidence_root / "human-decision" / "decision.json"
    for required_file, label in (
        (bandit_path, "Bandit JSON report"),
        (hygiene_path, "Repository hygiene report"),
        (security_review_path, "Human security review record"),
        (decision_path, "Human decision record"),
    ):
        if not required_file.is_file():
            raise ValueError(f"Required publication record is missing: {label}")

    reconstructed_pre_decision = build_pre_decision_evidence_manifest(evidence_root, candidate_digest)

    bandit_report_sha256 = _sha256_file(bandit_path)
    bandit_report = json.loads(bandit_path.read_text(encoding="utf-8"))
    hygiene_report = json.loads(hygiene_path.read_text(encoding="utf-8-sig"))
    security_review = json.loads(security_review_path.read_text(encoding="utf-8"))
    decision_record = json.loads(decision_path.read_text(encoding="utf-8"))

    verify_security_review_record(
        security_review,
        expected_candidate_digest=candidate_digest,
        bandit_report=bandit_report,
        hygiene_report=hygiene_report,
        expected_bandit_report_sha256=bandit_report_sha256,
        expected_candidate_commit=candidate_commit,
    )
    verify_human_decision_record(
        decision_record,
        expected_candidate_digest=candidate_digest,
        expected_pre_decision_evidence_digest=reconstructed_pre_decision["bundleDigest"],
        expected_candidate_commit=candidate_commit,
    )

    recomputed_final = build_evidence_manifest(evidence_root, candidate_digest)
    if recomputed_final != final_manifest:
        raise ValueError("Recomputed final evidence manifest does not match final_manifest.")
    if recomputed_final["bundleDigest"] == reconstructed_pre_decision["bundleDigest"]:
        raise ValueError("Final evidence bundle digest must differ from pre-decision evidence bundle digest.")
    return True


def seal(
    evidence_root: Path,
    manifest_path: Path,
    *,
    candidate_root: Path | None = None,
    candidate_sha: str | None = None,
    verify_publication: bool = False,
) -> bool:
    evidence_root.mkdir(parents=True, exist_ok=True)
    candidate_manifest_path = evidence_root / "candidate-manifest.json"
    candidate_digest = ""
    candidate_commit = ""
    if candidate_manifest_path.is_file():
        candidate = json.loads(candidate_manifest_path.read_text(encoding="utf-8"))
        candidate_digest = str(candidate.get("manifestDigest", ""))
        candidate_commit = str(candidate.get("candidateCommit", ""))
        entries = candidate.get("files")
        if not isinstance(entries, list) or manifest_digest(entries) != candidate_digest:
            raise ValueError("candidate-manifest.json failed internal digest verification.")
        if candidate_sha is not None and candidate_commit != candidate_sha:
            raise ValueError("candidate-manifest.json candidateCommit does not match expected candidate SHA.")
        if candidate_root is not None:
            actual_entries = build_manifest(candidate_root)
            if manifest_digest(actual_entries) != candidate_digest:
                raise ValueError("Publication candidate root differs from candidate-manifest.json.")

    results_path = evidence_root / "results.json"
    if results_path.is_file():
        has_security_review = (evidence_root / "security-review" / "review.json").is_file()
        has_decision = (evidence_root / "human-decision" / "decision.json").is_file()
        _validate_evidence_file_layout(
            evidence_root,
            require_security_review=has_security_review or verify_publication,
            allow_human_decision=has_decision or verify_publication,
        )

    manifest = build_evidence_manifest(evidence_root, candidate_digest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    verified = verify_evidence_manifest(evidence_root, manifest)
    if not verified:
        return False

    if verify_publication or (evidence_root / "human-decision" / "decision.json").is_file():
        pub_digest = candidate_digest
        if candidate_root is not None:
            pub_digest = manifest_digest(build_manifest(candidate_root))
        verify_publication_gate(
            evidence_root=evidence_root,
            final_manifest=manifest,
            publication_candidate_digest=pub_digest,
            expected_candidate_commit=candidate_sha or (candidate_commit if candidate_commit else None),
        )
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--candidate-root", type=Path)
    parser.add_argument("--candidate-sha")
    parser.add_argument("--verify-publication", action="store_true")
    args = parser.parse_args()
    try:
        verified = seal(
            args.evidence.resolve(),
            args.manifest.resolve(),
            candidate_root=args.candidate_root.resolve() if args.candidate_root else None,
            candidate_sha=args.candidate_sha,
            verify_publication=args.verify_publication,
        )
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"Evidence bundle could not be sealed: {exc}")
        return 1
    print(f"Evidence bundle integrity verified: {verified}")
    return 0 if verified else 1


if __name__ == "__main__":
    raise SystemExit(main())
