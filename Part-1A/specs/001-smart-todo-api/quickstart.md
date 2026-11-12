# Validation Quickstart

This is the planned Windows setup and validation flow, not an implementation.
The application and harness files in the tree are planned outputs. Authoritative
validation requires the separate trusted runner and its protected baseline,
approval store, and evidence archive described in `plan.md`.

## Prerequisites

- 64-bit Windows with Python 3.12 available to uv.
- uv installed and available on `PATH`.
- The reviewed Part-1A `pyproject.toml` and `uv.lock`, committed together.
- For authoritative validation, a configured trusted runner protected by a
  separate Windows identity/ACL or protected CI permissions.

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

Once implementation files exist, these commands run locally:

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

## Authoritative Validation and Acceptance

1. Invoke the Part-1A entrypoint:

   ```powershell
   .\.harness\run.ps1
   ```

   It must hand off to the protected runner. The trusted runner verifies the
   repository copies of `.harness/`, `tests/`, expected results, and controls
   against its protected baseline and approval records before running checks.
   It stages verified bytes before execution. Unauthorized changes fail with a
   runner-generated failure result and non-zero exit code. The Part-1A copies
   and their location do not themselves create a security boundary.

2. The runner executes mandatory tests, Ruff, Bandit, architecture, hygiene,
   network-isolation, and traceability checks. It generates results and writes
   them to `evidence/`, while retaining authoritative evidence in its protected
   store. Results are not manually edited.
3. A human reviews Bandit and repository-hygiene findings, records the final
   security review, then records an explicit `ACCEPT` or `REJECT`. Automated
   PASS never decides acceptance; publication remains blocked until human
   records are present and an `ACCEPT` is recorded.

No application tests or product-validation commands were run while preparing
these planning artifacts.
