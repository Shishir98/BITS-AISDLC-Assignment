# Assignment-1

This repository contains two assignment workspaces:

- `Part-1A/` contains the Smart Todo API project, its specification and plan,
  tests, validation-candidate harness, and evidence.
- `Part-1B/` contains the Part-1B Spec Kit configuration, scripts, templates,
  and workflow files.

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
