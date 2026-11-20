# Validation Quickstart

This quickstart describes the implemented Smart Todo API and local diagnostic
commands. Local runs are not authoritative. The GitHub Actions workflow and
bootstrap approval register are candidate implementations; D-01 remains blocked
until their review, approval, protected-main deployment, and actual workflow
run are verified.

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

## GitHub Candidate Validation and Acceptance

1. After the workflow and bootstrap baseline have been reviewed and approved
   through the protected `main` process, dispatch
   `.github/workflows/part-1a-candidate-validation.yml` from `main`. Supply the
   exact 40-character candidate commit SHA; branch names and tags are rejected.
2. The workflow checks out trusted `main` controls separately from the
   candidate, uses read-only repository permission, passes no secrets to
   candidate code, verifies approved digests, and creates a run-specific staged
   snapshot. It runs the locked tests, Ruff, and Bandit from staging and checks
   both staging and publication-candidate equality before and after execution.
   Logs and evidence are retained as a workflow artifact.
3. Review Bandit and repository-hygiene findings, then record the actual human
   security review and final ACCEPT/REJECT decision. Automated PASS never
   decides acceptance; publication remains blocked until human records are
   present and an ACCEPT is recorded.

The workflow and main-branch ruleset are not yet verified as an independent
canonical runner. Do not treat a local harness run or an unapproved workflow
run as authoritative. The following candidate diagnostic command is optional:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\.harness\run.ps1 -LocalDevelopment
```

This command intentionally reports local diagnostic status and does not
establish an independent trust boundary.
