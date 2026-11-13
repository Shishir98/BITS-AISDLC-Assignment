from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

EXCLUDED_DIRECTORIES = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".tox",
    "build",
    "dist",
    "data",
    "evidence",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".tmp", ".log"}
TRUST_METADATA = {
    ".harness/trust/bootstrap-baseline.json",
    ".harness/trust/approval-register.json",
}
APPROVAL_FIELDS = {
    "decision",
    "approver",
    "approved_at",
    "rationale",
    "source_commit",
    "approval_reference",
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _included(relative: str) -> bool:
    path = Path(relative)
    return not any(part in EXCLUDED_DIRECTORIES for part in path.parts) and path.suffix.lower() not in EXCLUDED_SUFFIXES


def build_manifest(root: Path) -> list[dict[str, str]]:
    entries = []
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if not _included(relative):
            continue
        if path.is_symlink():
            raise ValueError(f"Candidate contains a symbolic link: {relative}")
        if path.is_file():
            entries.append({"path": relative, "sha256": sha256_file(path)})
    return sorted(entries, key=lambda entry: entry["path"])


def manifest_digest(entries: list[dict[str, str]]) -> str:
    canonical = "\n".join(f'{entry["path"]}  {entry["sha256"]}' for entry in entries)
    return sha256_bytes(canonical.encode("utf-8"))


def verify_manifest(root: Path, expected: list[dict[str, str]]) -> bool:
    return build_manifest(root) == expected


def _copy_candidate(source: Path, destination: Path) -> list[dict[str, str]]:
    if destination.exists():
        raise FileExistsError(f"Run-specific staging path already exists: {destination}")
    destination.mkdir(parents=True)

    for current, directories, filenames in os.walk(source, followlinks=False):
        current_path = Path(current)
        relative_directory = current_path.relative_to(source)
        retained_directories = []
        for directory in directories:
            path = current_path / directory
            relative = (relative_directory / directory).as_posix()
            if not _included(relative):
                continue
            if path.is_symlink():
                raise ValueError(f"Candidate contains a symbolic link: {relative}")
            retained_directories.append(directory)
            (destination / relative).mkdir(parents=True, exist_ok=True)
        directories[:] = retained_directories

        for filename in filenames:
            source_file = current_path / filename
            relative = source_file.relative_to(source).as_posix()
            if not _included(relative):
                continue
            if source_file.is_symlink():
                raise ValueError(f"Candidate contains a symbolic link: {relative}")
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_file, target)
            original_mode = source_file.stat().st_mode
            target.chmod(0o555 if original_mode & stat.S_IXUSR else 0o444)

    for directory in sorted(
        (path for path in destination.rglob("*") if path.is_dir()),
        key=lambda item: len(item.parts),
        reverse=True,
    ):
        directory.chmod(0o555)
    destination.chmod(0o555)
    return build_manifest(destination)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _safe_file(root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts or "\\" in relative or "*" in relative or "?" in relative:
        raise ValueError(f"Baseline contains an unsafe path: {relative}")
    path = root / candidate
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"Baseline file is missing or unsafe: {relative}")
    return path


def _scoped_files(project_root: Path) -> set[str]:
    result: set[str] = set()
    for directory in ("tests", ".harness", ".github/workflows"):
        root = project_root / directory
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_symlink():
                raise ValueError(f"Candidate contains a symbolic link: {path.relative_to(project_root).as_posix()}")
            if path.is_file():
                relative = path.relative_to(project_root).as_posix()
                if _included(relative) and relative not in TRUST_METADATA:
                    result.add(relative)
    result.update(("pyproject.toml", "uv.lock"))
    inventory = _load_json(project_root / ".harness" / "instruction-files.json")
    if not isinstance(inventory, list):
        raise TypeError("Instruction inventory must be a JSON array")
    for entry in inventory:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise TypeError("Instruction inventory entry is malformed")
        result.add(entry["path"])
    return result


def _check_approval(register: dict[str, Any], baseline: dict[str, Any], baseline_path: Path) -> None:
    if register.get("status") != "APPROVED":
        raise ValueError("Bootstrap approval register is pending human review.")
    if sha256_file(baseline_path) != register.get("baseline_sha256"):
        raise ValueError("Bootstrap baseline digest does not match the approval register.")
    approval = register.get("approval")
    if not isinstance(approval, dict) or set(approval) != APPROVAL_FIELDS:
        raise ValueError("Approval record fields are incomplete.")
    if approval.get("decision") != "APPROVE":
        raise ValueError("Human approval decision is not APPROVE.")
    if any(not isinstance(approval.get(field), str) or not approval[field].strip() for field in APPROVAL_FIELDS):
        raise ValueError("Human approval metadata is incomplete.")
    if not re.fullmatch(r"[0-9a-f]{40}", approval["source_commit"]):
        raise ValueError("Human approval source commit must be a full lowercase SHA.")
    try:
        approved_at = approval["approved_at"]
        if approved_at.endswith("Z"):
            approved_at = f"{approved_at[:-1]}+00:00"
        datetime.fromisoformat(approved_at)
    except ValueError as exc:
        raise ValueError("Human approval date must be an ISO-8601 timestamp.") from exc

    files = baseline.get("files")
    if not isinstance(files, list):
        raise TypeError("Bootstrap baseline files must be a list.")
    expected = {entry.get("path") for entry in files if isinstance(entry, dict)}
    if len(expected) != len(files) or None in expected:
        raise ValueError("Bootstrap baseline contains malformed or duplicate files.")
    instruction_files = register.get("instruction_files")
    if not isinstance(instruction_files, list) or len(instruction_files) != 10:
        raise ValueError("The consolidated register must contain exactly ten instruction files.")
    for entry in instruction_files:
        if not isinstance(entry, dict) or not entry.get("approval_reference"):
            raise ValueError("Every inventoried instruction file needs its human approval reference.")
        if entry["approval_reference"] != approval["approval_reference"]:
            raise ValueError("Instruction approval references must match the consolidated approval.")


def _write_github_output(path: str | None, ready: bool) -> None:
    if path:
        with Path(path).open("a", encoding="utf-8") as handle:
            handle.write(f"ready={'true' if ready else 'false'}\n")


def prepare(args: argparse.Namespace) -> int:
    evidence = Path(args.evidence).resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    preflight_path = evidence / "bootstrap-preflight.json"
    try:
        candidate_sha = args.candidate_sha
        if not re.fullmatch(r"[0-9a-f]{40}", candidate_sha):
            raise ValueError("Candidate commit must be a full lowercase 40-character SHA.")
        trusted_root = Path(args.trusted_root).resolve()
        trusted_repo_root = Path(args.trusted_repo_root).resolve()
        candidate_root = Path(args.candidate_root).resolve()
        baseline_path = trusted_root / ".harness" / "trust" / "bootstrap-baseline.json"
        register_path = trusted_root / ".harness" / "trust" / "approval-register.json"
        baseline = _load_json(baseline_path)
        register = _load_json(register_path)
        _check_approval(register, baseline, baseline_path)

        trusted_files = baseline.get("trusted_files", [])
        for entry in trusted_files:
            path = _safe_file(trusted_repo_root, entry["path"])
            if sha256_file(path) != entry["sha256"]:
                raise ValueError(f"Trusted control digest mismatch: {entry['path']}")

        project_files = baseline["files"]
        expected_paths = {entry["path"] for entry in project_files}
        actual_paths = _scoped_files(candidate_root)
        if actual_paths != expected_paths:
            missing = sorted(expected_paths - actual_paths)
            extra = sorted(actual_paths - expected_paths)
            raise ValueError(f"Controlled file set mismatch; missing={missing}, extra={extra}")
        for entry in project_files:
            path = _safe_file(candidate_root, entry["path"])
            if sha256_file(path) != entry["sha256"]:
                raise ValueError(f"Candidate control/test digest mismatch: {entry['path']}")

        inventory = _load_json(candidate_root / ".harness" / "instruction-files.json")
        if inventory != register["instruction_files"]:
            raise ValueError("Candidate instruction inventory differs from the approved consolidated register.")
        commit = subprocess.run(
            ["git", "-C", str(candidate_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if commit != candidate_sha:
            raise ValueError("Checked out candidate commit does not match the explicit SHA.")

        stage = Path(args.stage).resolve()
        entries = _copy_candidate(candidate_root, stage)
        manifest = {
            "schemaVersion": 1,
            "candidateCommit": candidate_sha,
            "manifestDigest": manifest_digest(entries),
            "files": entries,
        }
        _write_json(evidence / "candidate-manifest.json", manifest)
        _write_json(preflight_path, {"status": "READY", "candidateCommit": candidate_sha})
        _write_github_output(args.github_output, True)
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        _write_json(preflight_path, {"status": "BLOCKED", "reason": str(exc)})
        _write_github_output(args.github_output, False)
        print(f"Candidate validation blocked: {exc}")
        return 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trusted-root", required=True)
    parser.add_argument("--trusted-repo-root", required=True)
    parser.add_argument("--candidate-root", required=True)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--github-output")
    return prepare(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
