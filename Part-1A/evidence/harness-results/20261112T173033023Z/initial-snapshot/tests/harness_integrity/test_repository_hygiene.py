from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
POWERSHELL = os.environ.get("POWERSHELL_EXE", "powershell.exe")
HYGIENE_SCRIPT = PROJECT_ROOT / ".harness" / "hygiene.ps1"


def _run_hygiene(project: Path, output: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(HYGIENE_SCRIPT),
            "-ProjectRoot",
            str(project),
            "-TrackedRoot",
            str(project),
            "-OutputDirectory",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_at026_synthetic_scanner_fixtures_detect_tracked_secret_like_files(tmp_path: Path) -> None:
    repository = tmp_path / "synthetic-repository"
    output = tmp_path / "scanner-output"
    repository.mkdir()
    subprocess.run(["git", "init", str(repository)], capture_output=True, check=True)

    fixtures = {
        ".env": "API_" + "TOKEN=" + "fixture-" + "only-never-a-real-token-123456",
        "fake-key.pem": "-----BEGIN " + "PRIVATE KEY-----\nFIXTURE ONLY\n-----END " + "PRIVATE KEY-----",
        "credentials.txt": "pass" + "word=" + "fixture-" + "only-never-a-real-password-123456",
    }
    for filename, contents in fixtures.items():
        (repository / filename).write_text(contents, encoding="utf-8")
    subprocess.run(["git", "-C", str(repository), "add", "."], capture_output=True, check=True)

    result = _run_hygiene(repository, output)
    assert result.returncode == 1
    report = json.loads((output / "hygiene.json").read_text(encoding="utf-8-sig"))
    assert report["syntheticFixtureChecksPassed"] is True
    assert report["secretsOmitted"] is True
    found = {(item["path"], item["rule"]) for item in report["findings"]}
    assert (".env", "tracked-environment-file") in found
    assert ("fake-key.pem", "private-key") in found
    assert ("credentials.txt", "credential-like-value") in found
    assert all(value not in json.dumps(report) for value in ("fixture-only-never-a-real", "FIXTURE ONLY"))
