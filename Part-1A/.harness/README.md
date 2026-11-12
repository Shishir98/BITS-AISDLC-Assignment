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
Pytest's cache provider is disabled, Python bytecode is suppressed, and Ruff
and Python caches are redirected to the external gate-output directory and
removed after execution so they do not accumulate in the staged candidate or
preserved run bundle.

The fixed sequence is:

1. Compare source and staged candidate manifests.
2. Verify instruction inventory paths, exact keys, current SHA-256 values, and
   approval references.
3. Record the protected-runner/identity boundary as blocked when it is not
   independently demonstrated.
4. Record Windows persistence readiness as D-05 `BLOCKED` until an approved
   Windows atomic-visibility strategy and supported-filesystem evidence exist.
   The AT-014 rollback fault-injection tests do not establish atomic visibility.
5. Run Ruff against `src/` and `tests/`.
6. Run Bandit against `src/`; preserve raw stdout, stderr, exit code, and a
   separate JSON copy when stdout is valid JSON. Findings are never suppressed
   or given an automated human disposition.
7. Collect pytest node IDs, then run every pytest test discoverable under
   `tests/` and write JUnit XML. The traceability gate requires an exact match
   between each configured normalized file/function node ID, pytest
   collection, and one JUnit case. It reports AC ID, AT ID, test file, test
   name, node ID, execution status, and output references. Missing tests,
   failed tests, or partial coverage fail the mandatory gate. Expected unit,
   persistence, concurrency, API-contract, error-handling, and harness-
   integrity directories are also reported when absent.
8. Check tracked paths and candidate text for environment files,
   credential-like values, private keys, and generated data. The scanner
   verifies itself against safe synthetic environment/credential/key fixtures
   stored only in the external evidence directory. Findings report paths and
   rule names, never matched secret values.
9. Record missing human Bandit-review and final-decision records as blocked;
   the runner does not create or infer either record.
10. Recalculate the source candidate digest and record whether it changed.

The runner continues independent diagnostic gates after ordinary lint, test,
security, or hygiene failures. It does not record ACCEPT/REJECT or a human
Bandit disposition. `results.json` contains gate commands, status, exit code,
timestamps, output references, and the candidate digest. Failure reports retain
the observed gate output.

## Current coverage limitation

Tests are organized under `tests/unit/`, `tests/api_contract/`,
`tests/persistence/`, `tests/concurrency/`, `tests/error_handling/`, and
`tests/harness_integrity/`. The original API tests are preserved in
`tests/api_contract/test_legacy_api.py`; they supplement, rather than replace,
the exact AT-001 through AT-029 node mappings in `mandatory-checks.json`.
Coverage and execution are distinct: a mapped case can still fail, and
criteria involving protected baselines, approval workflows, publication
integrity, or human records remain explicitly partial because those trusted
resources are unavailable here.

AT-008 verifies that omitted creation priority defaults to `Medium`, explicit
null is rejected for create and PATCH, valid priorities are accepted, invalid
values return `422`, and rejected or omitted PATCH values do not mutate stored
state. AT-014 is assessed as partial: rollback fault-injection tests verify
failure handling but do not establish Windows atomic visibility. D-01 and
D-05 remain unresolved regardless of local test results.
