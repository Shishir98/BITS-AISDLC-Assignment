# Assignment-1

This repository contains two assignment workspaces:

- `Part-1A/` contains the Smart Todo API project, its specification and plan,
  tests, validation-candidate harness, and evidence.
- `Part-1B/` contains a stateless natural-language reminder agent, its Spec Kit
  artifacts, tests, local Ollama configuration, evaluation harness, and
  preserved evidence.

## Submission status

- Part 1B has completed its actual-local-model evaluation and human ACCEPT.
- Part 1A has complete local candidate evidence (60 passing tests, Ruff PASS,
  Bandit PASS with zero findings, and hygiene PASS), and a human ACCEPT is
  recorded for the reviewed candidate. Protected workflow execution and
  publication remain separate gates that require GitHub authentication and
  branch/workflow verification.

## Part-1B setup and validation

Part-1B interprets reminder requests as validated proposals. It does not store,
schedule, or deliver reminders. The application uses a locally installed
Ollama model; see [the Part-1B README](Part-1B/README.md) for cloud-disabled
runtime setup and evaluation details.

From the repository root, install the locked dependencies and run the offline
checks:

```powershell
Set-Location .\Part-1B
uv sync --locked
uv run pytest
uv run ruff check src tests .harness
```

The actual-model evaluation is separate from offline testing and requires the
verified local Ollama setup:

```powershell
uv run python .harness/run_evaluation.py
```

Evaluation results, run provenance, and repair history are preserved under
`Part-1B/evidence/`.

## Part-1A setup and validation

Part-1A targets Python 3.12 and uses `uv` with the locked dependencies in
`Part-1A/pyproject.toml` and `Part-1A/uv.lock`.

From the repository root:

```powershell
Set-Location .\Part-1A
uv sync --locked
uv run --active --locked --no-sync pytest -q -p no:cacheprovider tests
```

The local candidate harness can be run with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\.harness\run.ps1 -LocalDevelopment
```

That runner is diagnostic-only. D-05 was resolved on 2026-11-13 by the
human-approved feature specification v1.4.0 and Constitution v2.0.0 amendments,
which retain JSON persistence and replace the unsupported Windows
atomic-visibility and crash-durability guarantee with an application-level
backup, byte-verification, restoration, and fail-closed recovery contract.
D-01's custom-bootstrap-only portions of AC-023 and AC-024 are waived by the
owner. That waiver does not establish a protected workflow run or waive the
independent AC-022 execution requirements; protected execution remains
`NOT VERIFIED`. The local harness reports automated results separately from
`WAIVED` and `NOT VERIFIED` portions. Local test results and candidate runs are
diagnostic only and do not constitute authoritative validation or human
acceptance. Human security review (T044) and the final decision (T045) remain
open for the student.
