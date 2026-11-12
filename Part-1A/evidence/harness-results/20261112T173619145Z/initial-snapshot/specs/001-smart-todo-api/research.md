# Phase 0 Research

Research used official Python, FastAPI, Pydantic, pytest, Microsoft Win32, and uv
documentation plus a local uv resolver run. Recommendations below are
constrained to the feature specification; they do not add application
capabilities.

## R-01: JSON Replacement and Windows Behavior

**Provisional strategy**: Use a temporary file created in the destination
directory, write the complete candidate JSON, flush and close the handle, then
call `os.replace(temp_path, target_path)`. Keep the prior in-memory state until
replacement succeeds. Remove an uncommitted temporary file after failure,
closing its handle before cleanup.

**Rationale**: `tempfile.mkstemp(dir=target.parent)` keeps the temporary file on
the same filesystem, and `os.replace` replaces an existing destination when
permitted. Closing handles before replacement/cleanup is important for Windows
file-sharing behavior. The prior state is not published when a write or replace
operation fails.

**Alternatives considered**: Write directly to the target (rejected because a
partial write could corrupt the previous document); use a temporary file in a
different directory (rejected because a cross-filesystem replace may fail).

**Windows limitation / blocker**: Python 3.12 documents atomic replacement with
the qualification that atomicity is a POSIX requirement; it does not establish
an atomic-visibility guarantee for `os.replace` on Windows. The reviewed Win32
alternatives do not close this evidence gap:

- `ReplaceFileW` is explicitly designed to replace one file with another and
  combines operations that otherwise require several calls. Its Microsoft
  documentation describes failure outcomes where the replaced file may no
  longer exist at its original path or may be moved to another name. It does not
  formally promise atomic visibility for every supported filesystem/failure
  condition.
- `MoveFileExW` supports `MOVEFILE_REPLACE_EXISTING`, but its documentation
  does not state an atomic-visibility guarantee. `MOVEFILE_WRITE_THROUGH` does
  not establish atomic visibility; the documented flush guarantee is limited to
  the cross-volume copy/delete path.

Atomic visibility and crash durability are separate properties. None of these
documents proves both for the assignment's Windows setup. Keep the existing
data-integrity requirement unchanged and D-05 blocked. Do not select either
Win32 API as compliant without additional platform-specific evidence and a
reviewed recovery design; do not make a crash-durability claim.

Sources:

- [Python 3.12 `tempfile.mkstemp`](https://docs.python.org/3.12/library/tempfile.html#tempfile.mkstemp)
- [Python 3.12 `NamedTemporaryFile` and Windows behavior](https://docs.python.org/3.12/library/tempfile.html#tempfile.NamedTemporaryFile)
- [Python 3.12 `os.replace`](https://docs.python.org/3.12/library/os.html#os.replace)
- [Python 3.12 `os.remove`](https://docs.python.org/3.12/library/os.html#os.remove)
- [Microsoft `ReplaceFileW`](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-replacefilew)
- [Microsoft `MoveFileExW`](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexw)

## R-02: Single-Process Mutation Coordination

**Decision**: Use one shared standard-library `threading.Lock` around the full
read/modify/persist/publish operation. Keep candidate state separate until the
atomic replacement reports success. Use synchronous FastAPI route functions for
the synchronous repository; FastAPI dispatches normal `def` operations through
its worker thread pool.

**Rationale**: The lock provides mutual exclusion across request threads and the
specified feature excludes independent process writers. It does not impose FIFO
ordering, which agrees with the specification's statement that request-to-ID
assignment among concurrent requests is unspecified.

**Alternatives considered**: An `asyncio.Lock` (not needed for synchronous file
operations); no lock (would allow colliding IDs and lost updates); a
cross-process lock (outside specified scope).

Sources:

- [Python 3.12 `threading.Lock`](https://docs.python.org/3.12/library/threading.html#lock-objects)
- [FastAPI concurrency and `def`/`async def`](https://fastapi.tiangolo.com/async/)

## R-03: API and Persistence Testing

**Decision**: Use pytest with FastAPI's in-process `TestClient`, isolated store
paths via pytest's `tmp_path`, and `monkeypatch` for controlled write/replace
failures. Parametrize stored-data validation cases. Run the authoritative tests
from the independent protected harness, not from an agent-writable copy.

**Rationale**: Passing the app directly to `TestClient` exercises the HTTP
contract without launching a separate server or relying on external network
services. Temporary directories isolate test data; controlled failures verify
rollback and preservation behavior.

**Dependency note**: FastAPI documents that HTTPX is required to use
`TestClient`; the user-approved planning set includes HTTPX and Uvicorn.
Resolved versions are recorded in R-04.

Sources:

- [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [pytest `tmp_path`](https://docs.pytest.org/en/stable/how-to/tmp_path.html)
- [pytest `monkeypatch`](https://docs.pytest.org/en/stable/how-to/monkeypatch.html)
- [pytest parametrization](https://docs.pytest.org/en/stable/how-to/parametrize.html)
- [Pydantic models](https://docs.pydantic.dev/latest/concepts/models/)

## R-04: Dependency Resolution with uv

**Decision for planning**: Use uv and commit the project `uv.lock`. Resolved the
requested direct dependencies together in a temporary, bare uv project using
uv 0.13.7 on Windows with CPython 3.12.0. The resolver produced one compatible
lock solution with 31 total packages; no packages were installed and no
application files were created for this check.

| Purpose | Package | Resolved version |
|---|---|---:|
| Runtime | FastAPI | 0.162.4 |
| Runtime | Pydantic | 2.14.3 |
| Development/test | pytest | 9.2.0 |
| Development/test | HTTPX | 0.28.1 |
| Development/quality | Ruff | 0.17.4 |
| Development/security | Bandit | 1.9.4 |
| Local serving | Uvicorn | 0.54.0 |

These are a resolver-checked compatible set for the stated Python 3.12 target,
not arbitrary version guesses. Add the runtime packages to project dependencies,
and pytest, HTTPX, Ruff, Bandit, and Uvicorn to the development dependency group.
Generate and commit the project lockfile with uv before implementation; use
`uv sync --locked` and `uv run --locked` thereafter. Re-resolve only through an
approved dependency change and review the resulting lock diff.

## R-05: Trusted Harness Boundary

Part-1A must contain `src/`, `tests/`, `.harness/`, and `evidence/`. The
repository copies of mandatory tests, expected results, scripts, and configs
remain agent-editable; their presence outside `src/` or outside VS Code does not
make them trusted. The authoritative runner, baseline manifest, approval
records, verified staging, and evidence archive must be controlled by a
separately administered Windows identity/ACL or protected CI permissions.

The runner verifies repository-file digests against that protected baseline
before execution, stages the verified bytes, and runs the staged snapshot.
Legitimate changes are accepted only after a human approval record with change
scope and old/new digests is stored through the protected channel. Local
`evidence/` files are runner-generated mirrors; the protected archive is
authoritative. If the coding agent shares the trusted identity, has admin
rights, or can change CI controls, the boundary fails. D-01 remains an
implementation blocker until the actual assignment environment demonstrates
separation.

## Unresolved Research Constraints

- No reviewed Windows replacement API documents the required atomic-visibility
  guarantee under the target conditions; D-05 remains blocked.
- The protected runner's actual host, separate identity, and permissions must be
  established by the human/assignment owner; D-01 remains blocked.
- Resolved package versions and the generated `pyproject.toml`/`uv.lock` are
  ready for human review and must be committed together before application
  implementation.
