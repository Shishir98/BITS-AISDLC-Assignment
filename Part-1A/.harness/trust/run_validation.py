from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from prepare_candidate import build_manifest, manifest_digest, verify_manifest

WINDOWS_ENVIRONMENT_ALLOWLIST = {
    "APPDATA",
    "COMSPEC",
    "HOMEDRIVE",
    "HOMEPATH",
    "LOCALAPPDATA",
    "PATH",
    "PATHEXT",
    "PROGRAMDATA",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "WINDIR",
}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _candidate_environment(
    stage: Path,
    evidence: Path,
    environment_directory: Path,
    uv_cache: Path,
    inherited: dict[str, str] | None = None,
) -> dict[str, str]:
    source = os.environ if inherited is None else inherited
    environment = {key: source[key] for key in WINDOWS_ENVIRONMENT_ALLOWLIST if key in source}
    environment.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "PYTHONPATH": str(stage / "src"),
            "PYTEST_ADDOPTS": "-p no:cacheprovider",
            "RUFF_CACHE_DIR": str(evidence / "ruff-cache"),
            "UV_CACHE_DIR": str(uv_cache.resolve()),
            "UV_NO_CONFIG": "1",
            "UV_PROJECT_ENVIRONMENT": str(environment_directory.resolve()),
        }
    )
    return environment


def _run_gate(
    name: str,
    command: list[str],
    cwd: Path,
    environment: dict[str, str],
    output_directory: Path,
) -> dict[str, Any]:
    output_directory.mkdir(parents=True, exist_ok=True)
    started = _utc_now()
    start_time = time.monotonic()
    try:
        result = subprocess.run(command, cwd=cwd, env=environment, capture_output=True, text=True, check=False)
        stdout = result.stdout
        stderr = result.stderr
        exit_code = result.returncode
    except OSError as exc:
        stdout = ""
        stderr = str(exc)
        exit_code = 127
    (output_directory / f"{name}.stdout.txt").write_text(stdout, encoding="utf-8")
    (output_directory / f"{name}.stderr.txt").write_text(stderr, encoding="utf-8")
    gate: dict[str, Any] = {
        "name": name,
        "command": command,
        "startedAt": started,
        "finishedAt": _utc_now(),
        "durationSeconds": round(time.monotonic() - start_time, 3),
        "exitCode": exit_code,
        "stdout": f"{name}.stdout.txt",
        "stderr": f"{name}.stderr.txt",
    }
    if name == "bandit":
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            gate["machineReadableFindings"] = "unavailable"
        else:
            findings_path = output_directory / "bandit.json"
            findings_path.write_text(json.dumps(parsed, indent=2) + "\n", encoding="utf-8")
            gate["machineReadableFindings"] = "bandit.json"
    if name == "pytest":
        junit_path = output_directory.parent / "junit.xml"
        if junit_path.is_file():
            try:
                root = ET.parse(junit_path).getroot()
            except ET.ParseError:
                gate["testCount"] = 0
                gate["failureCount"] = 1
            else:
                test_cases = root.findall(".//testcase")
                gate["testCount"] = len(test_cases)
                gate["failureCount"] = sum(
                    case.find("failure") is not None
                    or case.find("error") is not None
                    or case.find("skipped") is not None
                    for case in test_cases
                )
    return gate


def _verify_traceability(stage: Path, evidence: Path) -> dict[str, Any]:
    output_directory = evidence / "gates"
    output_directory.mkdir(parents=True, exist_ok=True)
    stdout_path = output_directory / "traceability.stdout.txt"
    stderr_path = output_directory / "traceability.stderr.txt"
    try:
        configuration = json.loads((stage / ".harness" / "mandatory-checks.json").read_text(encoding="utf-8"))
        junit = ET.parse(evidence / "junit.xml").getroot()
        criteria = configuration["traceability"]
        expected_ats = {f"AT-{number:03d}" for number in range(1, 30)}
        actual_acs = {entry["ac"] for entry in criteria}
        actual_ats = {entry["at"] for entry in criteria}
        if (
            len(criteria) != 29
            or len(actual_acs) != len(criteria)
            or len(actual_ats) != len(criteria)
            or actual_acs != {f"AC-{number:03d}" for number in range(1, 30)}
            or actual_ats != expected_ats
        ):
            raise ValueError("Traceability configuration must map all 29 acceptance criteria exactly once.")
        if set(configuration["pytest"]["acceptanceTestIds"]) != expected_ats:
            raise ValueError("Pytest acceptance-test inventory differs from the 29-criterion map.")

        collected = {
            (case.attrib.get("classname", ""), case.attrib.get("name", "")): case
            for case in junit.findall(".//testcase")
        }
        cases = []
        missing = []
        failed = []
        for criterion in criteria:
            tests = criterion.get("tests", [])
            if not tests:
                missing.append(criterion["ac"])
            for expected in tests:
                key = (expected["className"], expected["name"])
                case = collected.get(key)
                passed = (
                    case is not None
                    and case.find("failure") is None
                    and case.find("error") is None
                    and case.find("skipped") is None
                )
                cases.append(
                    {
                        "ac": criterion["ac"],
                        "at": criterion["at"],
                        "nodeId": expected["nodeId"],
                        "executed": case is not None,
                        "passed": passed,
                    }
                )
                if case is None:
                    missing.append(expected["nodeId"])
                elif not passed:
                    failed.append(expected["nodeId"])
        passed = not missing and not failed
        summary = {
            "status": "PASS" if passed else "FAIL",
            "acceptanceCriterionCount": len(actual_acs),
            "acceptanceTestCount": len(actual_ats),
            "mappedCaseCount": len(cases),
            "missing": missing,
            "failed": failed,
            "cases": cases,
        }
        stdout_path.write_text(
            f"Acceptance criteria: {len(actual_acs)}; mapped tests: {len(actual_ats)}; "
            f"mapped cases: {len(cases)}; status: {summary['status']}\n",
            encoding="utf-8",
        )
        stderr_path.write_text("", encoding="utf-8")
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError, ET.ParseError) as exc:
        summary = {
            "status": "FAIL",
            "acceptanceCriterionCount": 0,
            "acceptanceTestCount": 0,
            "mappedCaseCount": 0,
            "missing": [],
            "failed": [],
            "error": str(exc),
            "cases": [],
        }
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text(str(exc) + "\n", encoding="utf-8")
    (evidence / "traceability.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return {
        "name": "traceability",
        "command": "Trusted XML verification of mandatory-checks.json against pytest JUnit results",
        "startedAt": _utc_now(),
        "finishedAt": _utc_now(),
        "exitCode": 0 if summary["status"] == "PASS" else 1,
        "stdout": "traceability.stdout.txt",
        "stderr": "traceability.stderr.txt",
        "report": "traceability.json",
    }


def run_validation(args: argparse.Namespace) -> int:
    source = Path(args.source).resolve()
    stage = Path(args.stage).resolve()
    evidence = Path(args.evidence).resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    manifest_path = evidence / "candidate-manifest.json"
    start = _utc_now()
    gates: list[dict[str, Any]] = []
    candidate_digest = ""
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entries = manifest["files"]
        candidate_digest = manifest["manifestDigest"]
        if (
            candidate_digest != manifest_digest(entries)
            or not verify_manifest(source, entries)
            or not verify_manifest(stage, entries)
        ):
            raise ValueError("Staged candidate failed pre-execution integrity verification.")
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        (evidence / "pre-execution-integrity.txt").write_text(str(exc), encoding="utf-8")
        return 2

    environment = _candidate_environment(
        stage,
        evidence,
        Path(args.environment),
        Path(args.uv_cache),
    )
    (evidence / "gates").mkdir(exist_ok=True)

    commands = [
        ("dependency-sync", ["uv", "sync", "--project", str(stage), "--locked", "--python", "3.12"]),
        ("python-version", ["python", "--version"]),
        ("uv-version", ["uv", "--version"]),
        (
            "pytest-version",
            ["uv", "run", "--project", str(stage), "--locked", "--no-sync", "python", "-m", "pytest", "--version"],
        ),
        ("ruff-version", ["uv", "run", "--project", str(stage), "--locked", "--no-sync", "ruff", "--version"]),
        ("bandit-version", ["uv", "run", "--project", str(stage), "--locked", "--no-sync", "bandit", "--version"]),
        (
            "pytest",
            [
                "uv",
                "run",
                "--project",
                str(stage),
                "--locked",
                "--no-sync",
                "python",
                "-m",
                "pytest",
                "-q",
                "--junitxml",
                str(evidence / "junit.xml"),
                "tests",
            ],
        ),
        (
            "ruff",
            ["uv", "run", "--project", str(stage), "--locked", "--no-sync", "ruff", "check", "src", "tests"],
        ),
        (
            "bandit",
            [
                "uv",
                "run",
                "--project",
                str(stage),
                "--locked",
                "--no-sync",
                "bandit",
                "-r",
                "src",
                "-f",
                "json",
            ],
        ),
    ]
    for name, command in commands:
        gates.append(_run_gate(name, command, stage, environment, evidence / "gates"))
        if name == "pytest":
            gates.append(_verify_traceability(stage, evidence))

    integrity_matches = verify_manifest(source, entries) and verify_manifest(stage, entries)
    publication_matches = build_manifest(source) == build_manifest(stage)
    results = {
        "schemaVersion": 1,
        "validationMode": "protected-main-candidate-validation",
        "authoritative": False,
        "humanDecision": None,
        "candidateCommit": manifest["candidateCommit"],
        "candidateDigest": candidate_digest,
        "startedAt": start,
        "finishedAt": _utc_now(),
        "postExecutionIntegrityMatches": integrity_matches,
        "publicationCandidateMatchesStagedSnapshot": publication_matches,
        "gates": gates,
    }
    (evidence / "results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    if not integrity_matches:
        (evidence / "post-execution-integrity.txt").write_text(
            "Staged files differ from the pre-execution candidate manifest.\n",
            encoding="utf-8",
        )
    return (
        0
        if integrity_matches and publication_matches and all(gate["exitCode"] == 0 for gate in gates)
        else 1
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--uv-cache", required=True)
    return run_validation(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
