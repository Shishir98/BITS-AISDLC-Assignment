# Phase 0 Research

Research used official Python, FastAPI, Pydantic, pytest, Microsoft Win32, and uv
documentation plus a local uv resolver run. Recommendations below are
constrained to the feature specification; they do not add application
capabilities.

## R-01: Application-Level JSON Backup and Recovery

**Approved strategy (D-05 amendment, human-approved 2026-11-13)**: Retain the
JSON store and serialize the complete candidate document to bytes before
touching the primary. For an existing store, capture its exact bytes, write
them to a uniquely named same-directory backup, close the file, and verify
those bytes before attempting replacement. Write and close the candidate in a
uniquely named same-directory temporary file, then use the existing
`os.replace` operation as a best-effort replacement mechanism. Read the primary
back and compare it byte-for-byte with the candidate before committing memory.
On an application-handled failure, restore from the verified backup using a
same-directory temporary file and verify the restored bytes. If the original
store was absent, remove a partially installed primary and verify absence. If
recovery cannot be verified, retain recovery material and fail closed. Cleanup
is permitted only after a verified transaction; cleanup failure does not undo
an already verified commit.

**Technical rationale**: Python documents `os.replace` as a replacement
operation, but its documented atomicity qualification does not establish
atomic visibility on Windows. The reviewed Microsoft `ReplaceFileW` and
`MoveFileExW` documentation likewise does not establish the former Windows
atomic-visibility requirement for all supported filesystem conditions. The
approved change therefore removes that guarantee rather than
claiming undocumented behavior. Same-directory files and closed handles follow
Python's documented temporary-file and Windows handling guidance. Byte
verification and a uniquely named backup provide the narrower application
recovery behavior required by the approved specification. Each transaction
uses the backup it just created and verifies it before relying on it; older
leftover backups are never selected.

**Failure boundary and explicit limitations**: These operations address
application-handled exceptions while the process can execute recovery code.
They do not guarantee OS-level atomic visibility during Windows replacement,
crash durability across sudden power loss, recovery after abrupt process
termination or OS failure during replacement, or hardware-level persistence
beyond documented application operations. `os.fsync` is retained for completed
file writes, but it does not extend the approved guarantee into those excluded
failure classes. No Win32 replacement API is substituted for `os.replace`.

**Alternatives considered**: Directly write the primary (rejected because a
partial write could damage prior contents); create transaction files in another
directory (rejected because same-directory placement avoids a cross-filesystem
replacement); select a Win32 API to claim atomicity or durability (rejected
because the reviewed official documentation does not substantiate those
claims).

Sources:

- [Python 3.12 `tempfile.mkstemp`](https://docs.python.org/3.12/library/tempfile.html#tempfile.mkstemp)
- [Python 3.12 `NamedTemporaryFile` and Windows behavior](https://docs.python.org/3.12/library/tempfile.html#tempfile.NamedTemporaryFile)
- [Python 3.12 `os.replace`](https://docs.python.org/3.12/library/os.html#os.replace)
- [Python 3.12 `os.remove`](https://docs.python.org/3.12/library/os.html#os.remove)
- [Python 3.12 `os.fsync`](https://docs.python.org/3.12/library/os.html#os.fsync)
- [Microsoft `ReplaceFileW`](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-replacefilew)
- [Microsoft `MoveFileExW`](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexw)

## R-02: Single-Process Mutation Coordination

**Decision**: Use one shared standard-library `threading.Lock` around the full
read/modify/persist/publish operation. Keep candidate state separate until
primary-file verification succeeds. Use synchronous FastAPI route functions
for the synchronous repository; FastAPI dispatches normal `def` operations
through its worker thread pool.

**Rationale**: The lock provides mutual exclusion across request threads and the
specified feature excludes independent process writers. It does not impose FIFO
ordering, which agrees with the specification's statement that request-to-ID
assignment among concurrent requests is unspecified. The service publishes a
candidate only after the repository has verified persisted candidate bytes.

**Alternatives considered**: An `asyncio.Lock` (not needed for synchronous file
operations); no lock (would allow colliding IDs and lost updates); a
cross-process lock (outside specified scope).

Sources:

- [Python 3.12 `threading.Lock`](https://docs.python.org/3.12/library/threading.html#lock-objects)
- [FastAPI concurrency and `def`/`async def`](https://fastapi.tiangolo.com/async/)

## R-03: API and Persistence Testing

**Decision**: Use pytest with FastAPI's in-process `TestClient`, isolated store
paths via pytest's `tmp_path`, and `monkeypatch` for controlled serialization,
write, backup, replacement, recovery, and cleanup failures. Parametrize
stored-data validation cases. Local candidate tests are diagnostic; authoritative
execution still requires the independent protected harness.

**Rationale**: Passing the app directly to `TestClient` exercises the HTTP
contract without launching a separate server or relying on external network
services. Temporary directories isolate test data; controlled failures verify
the application-handled restoration/absence and fail-closed paths. These tests
do not establish atomic visibility or crash durability.

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

## R-05: GitHub Validation Boundary

Part-1A must contain `src/`, `tests/`, `.harness/`, and `evidence/`. The
repository copies of mandatory tests, expected results, scripts, and configs
remain candidate-controlled; their location does not make them trusted. The
selected D-01 implementation is a manually dispatched GitHub Actions workflow
from protected `main`. It checks out the trusted workflow and explicit
candidate commit separately, uses `contents: read`, does not pass secrets to
candidate code, verifies approved digests, creates run-specific staging, and
checks integrity before and after execution. Logs and evidence are retained as
workflow artifacts.

The consolidated approval register remains pending until a human records the
approval details for the exact initial baseline and ten inventoried instruction
files. A branch ruleset by itself does not prove that the workflow is canonical
or independently administered. D-01 remains an implementation blocker until
the protected workflow and approval prerequisite are present on `main`, the
runner's trust boundary is verified, and an actual protected run succeeds.
Local `evidence/` files and candidate workflow runs are not independently
authoritative.

## Unresolved Research Constraints

- D-05 is resolved by the human-approved 2026-11-13 specification amendment;
  no Windows atomic-visibility or crash-durability guarantee is claimed.
- The protected GitHub workflow, exact branch ruleset controls, approval
  register, and trusted execution boundary must be verified by the
  human/assignment owner; no additional Windows account is part of the selected
  design and D-01 remains blocked.
- Resolved package versions and the generated `pyproject.toml`/`uv.lock` are
  ready for human review and must be committed together before application
  implementation.
