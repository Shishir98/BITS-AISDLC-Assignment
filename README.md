# Assignment-1

This repository contains two assignment workspaces:

- `Part-1A/` contains the Smart Todo API project, its specification and plan,
  tests, validation-candidate harness, and evidence.
- `Part-1B/` contains a stateless natural-language reminder agent, its Spec Kit
  artifacts, tests, local Ollama configuration, evaluation harness, and
  preserved evidence.

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

That runner is diagnostic-only. D-01 remains blocked because an independently
protected canonical runner and execution boundary have not been demonstrated.
D-05 remains blocked because an approved Windows atomic-visibility strategy
and supporting evidence have not been demonstrated. Local test results do not
resolve either governance or persistence-readiness gate.
