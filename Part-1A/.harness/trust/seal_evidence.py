from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def build_evidence_manifest(evidence_root: Path, candidate_digest: str) -> dict[str, Any]:
    files = []
    for path in evidence_root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"Evidence contains a symbolic link: {path.relative_to(evidence_root).as_posix()}")
        if path.is_file():
            files.append(
                {
                    "path": path.relative_to(evidence_root).as_posix(),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
    files.sort(key=lambda entry: entry["path"])
    canonical = "\n".join(f'{entry["path"]}  {entry["sha256"]}' for entry in files)
    return {
        "schemaVersion": 1,
        "candidateDigest": candidate_digest,
        "bundleDigest": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "files": files,
    }


def verify_evidence_manifest(evidence_root: Path, manifest: dict[str, Any]) -> bool:
    return build_evidence_manifest(evidence_root, manifest["candidateDigest"]) == manifest


def seal(evidence_root: Path, manifest_path: Path) -> bool:
    evidence_root.mkdir(parents=True, exist_ok=True)
    candidate_manifest_path = evidence_root / "candidate-manifest.json"
    candidate_digest = ""
    if candidate_manifest_path.is_file():
        candidate = json.loads(candidate_manifest_path.read_text(encoding="utf-8"))
        candidate_digest = candidate.get("manifestDigest", "")
    manifest = build_evidence_manifest(evidence_root, candidate_digest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return verify_evidence_manifest(evidence_root, manifest)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()
    try:
        verified = seal(args.evidence.resolve(), args.manifest.resolve())
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"Evidence bundle could not be sealed: {exc}")
        return 1
    print(f"Evidence bundle integrity verified: {verified}")
    return 0 if verified else 1


if __name__ == "__main__":
    raise SystemExit(main())
