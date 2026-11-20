# Validation Quickstart

This quickstart describes the implemented Smart Todo API and local diagnostic
commands. Local runs are not authoritative. The GitHub Actions workflow and
bootstrap files are repository candidates. The owner waived only the
custom-bootstrap portions of AC-023 and AC-024. The independent AC-022
protected-execution requirements remain `NOT VERIFIED`; the waiver does not
establish a protected workflow run or make a local run authoritative.

## Prerequisites

- 64-bit Windows with Python 3.12 available to uv.
- uv installed and available on `PATH`.
- The reviewed Part-1A `pyproject.toml` and `uv.lock`, committed together.
- For the future protected validation run, the workflow must be dispatched from
  the configured protected `main` branch with a full candidate commit SHA.

Check the tools before syncing:

```powershell
uv --version
uv python find 3.12
```

Install uv using the official installation instructions if it is unavailable:
[uv installation](https://docs.astral.sh/uv/getting-started/installation/).

## Environment and Store

From the Part-1A repository root, install the exact locked dependency set and
create the uv-managed environment:

```powershell
uv sync --locked
```

Commit `uv.lock` with `pyproject.toml` and keep them synchronized.
`--locked` makes validation fail rather than silently updating the lock.
Runtime dependencies are FastAPI and Pydantic; the development group contains
pytest, HTTPX, Ruff, Bandit, and Uvicorn.

The default JSON store is `data/tasks.json`, relative to the process working
directory. `/data/` is Git-ignored. To use a different local store, set
`SMART_TODO_STORE_PATH`; custom paths must also be outside tracked files or
explicitly Git-ignored. The application factory's explicit `Path` takes
precedence over the environment variable and is used by isolated tests.

```powershell
New-Item -ItemType Directory -Force data | Out-Null
$env:SMART_TODO_STORE_PATH = Join-Path $PWD 'data\tasks.json'
```

Unset the variable to use the default. Do not commit `.env` files, credentials,
private keys, or the runtime store.

## Local Development Checks

```powershell
uv run --locked pytest
uv run --locked ruff check .
uv run --locked bandit -r src
```

The required thresholds are zero Ruff violations, all mandatory tests passing,
and Bandit execution with its findings reviewed and documented. Automated
application tests use an in-process ASGI client and must make no external
network requests. For a local demonstration:

```powershell
uv run --locked uvicorn smart_todo.app:app --app-dir src --reload
```

## Candidate Validation and Acceptance

Run the local candidate harness from the Part-1A root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\.harness\run.ps1 -LocalDevelopment
```

It stages Part-1A, snapshots and hashes the root workflow used by harness tests,
and runs Ruff, Bandit, pytest/traceability, and repository hygiene. The output
reports each criterion/portion as `PASS`, `WAIVED`, or `NOT VERIFIED`; the
overall result remains `NOT VERIFIED` while protected workflow execution or
human-only actions are outstanding. Exit code 0 means no local automated gate
failed; it does not mean the assignment was accepted or validated by a trusted
runner.

The owner waiver covers only the custom-bootstrap portions of AC-023 and
AC-024. It does not waive AC-022 protected execution. Do not claim that the
repository workflow or an ordinary local run is an independently verified
canonical runner. The student must still perform T044's human security review
and T045's human ACCEPT/REJECT decision after the required final automated
evidence is available. Automated checks never create or infer either record.
