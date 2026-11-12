# Part-1A validation candidate harness

## Trust boundary

The scripts and controls in this directory are **untrusted repository
candidates**. They are not a canonical runner, do not verify themselves against
a separately protected baseline, and do not establish an independent Windows
identity/ACL or protected-CI boundary. D-01 therefore remains blocked. An
ordinary local run is not an authoritative validation and must not be used as
an acceptance, security-review, or publication decision.

The `instruction-files.json` entries record the current file paths and digests.
Their empty `approval_reference` values explicitly mean that no human approval
record was supplied. Do not invent references or treat those digests as a
trusted baseline. A human administrator must review and approve the exact
candidate out of band, then enroll it through the protected canonical-runner
process before any authoritative execution.

## Local diagnostic run

From `Part-1A`, after installing the locked project dependencies, run:

```powershell
uv sync --locked
powershell -NoProfile -ExecutionPolicy Bypass -File .\.harness\run.ps1 -LocalDevelopment
```

The runner deliberately requires `-LocalDevelopment`. Without it, it exits
non-zero before running application checks because this is not the canonical
runner. The diagnostic command stages a SHA-256-manifested snapshot outside the
repository and executes the staged candidate, not the mutable working tree.
It still exits non-zero while D-01 is blocked, while any gate fails, or while
any AC lacks complete mapped executable coverage.

By default, output is stored under
`$env:LOCALAPPDATA\SmartTodoValidation\Part-1A\<run-id>`. Pass `-EvidenceRoot
<absolute-path>` to select another location outside the project. Each run
contains initial, staged, and final candidate snapshots, a sorted validation
candidate manifest, per-gate stdout/stderr, JUnit XML, Bandit JSON, a
traceability CSV/JSON report, repository-hygiene output, failure reports, and
`results.json`. A detached `<run-id>.evidence-manifest.json` is written next
to the run directory and hashes the complete run bundle (excluding itself)
while binding it to the candidate digest. Evidence is outside the candidate
digest; the local evidence manifest is not protected or authoritative.

The gate scripts use `uv run --active --no-sync`; they execute from the locked
environment prepared by `uv sync --locked` and do not install packages during
a validation run. Python imports for pytest are directed to the staged `src/`.

The fixed sequence is:

1. Compare source and staged candidate manifests.
2. Verify instruction inventory paths, exact keys, current SHA-256 values, and
   approval references.
3. Record the protected-runner/identity boundary as blocked when it is not
   independently demonstrated.
4. Run Ruff against `src/` and `tests/`.
5. Run Bandit against `src/`; preserve raw stdout, stderr, exit code, and a
   separate JSON copy when stdout is valid JSON. Findings are never suppressed
   or given an automated human disposition.
6. Run every pytest test discoverable under `tests/`, write JUnit XML, and
   generate an AC/AT-to-file/test-name traceability report. Missing or partial
   coverage is a failed mandatory gate. Expected unit, persistence,
   concurrency, API-contract, and harness-integrity directories are also
   reported when absent.
7. Check tracked paths and candidate text for environment files,
   credential-like values, private keys, and generated data. The scanner
   verifies itself against safe synthetic environment/credential/key fixtures
   stored only in the external evidence directory. Findings report paths and
   rule names, never matched secret values.
8. Record missing human Bandit-review and final-decision records as blocked;
   the runner does not create or infer either record.
9. Recalculate the source candidate digest and record whether it changed.

The runner continues independent diagnostic gates after ordinary lint, test,
security, or hygiene failures. It does not record ACCEPT/REJECT or a human
Bandit disposition. `results.json` contains gate commands, status, exit code,
timestamps, output references, and the candidate digest. Failure reports retain
the observed gate output.

## Current coverage limitation

The submitted tests currently consist of `tests/test_api.py`. Some criteria
have partial behavioral checks; most have no test. The status and exact gaps
are recorded for AT-001 through AT-029 in `mandatory-checks.json` and emitted
as `traceability.csv`/`traceability.json`. These tests are not modified or
weakened by the harness. The traceability gate stays failed until complete
approved test coverage exists and the candidate is enrolled in the protected
runner process.
