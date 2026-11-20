# Implementation Plan: Smart Todo & Task Management API

**Branch**: `001-smart-todo-api` | **Date**: 2026-11-11 | **Spec**:
[spec.md](./spec.md)

**Status**: ACCEPT

**Approved**: 2026-11-12

**Amendment status**: This dependent plan update reflects the human-approved
feature specification v1.4.0 amendment dated 2026-11-13; the plan retains its
original 2026-11-12 approval record.

**Planning basis**: The original plan and feature specification v1.3.0 were
approved on 2026-11-12. The feature specification was amended to v1.4.0 with
explicit human approval dated 2026-11-13; that amendment resolves D-05 by
replacing the unsupported platform guarantee with an application-level
recovery contract. The protected runner boundary D-01 remains open.

## Summary

Build a small, single-process FastAPI service with explicit Pydantic request,
response, domain, and stored-document models. A business service owns task rules
and mutation coordination. A JSON repository lazily reads and fully validates
the configured local document, then persists complete candidates through
uniquely named same-directory temporary and verified backup files, best-effort
replacement, and byte verification. In-memory state advances only after the
primary matches the candidate bytes. Application-handled failures attempt
byte-exact restoration (or verified restoration of absence) and fail closed if
recovery cannot be verified; this does not claim Windows atomic visibility or
crash durability. Part-1A contains the required `src/`, `tests/`,
`.harness/`, and `evidence/` structure. A separate access-controlled runner
provides the trusted validation boundary; its external location alone is not
protection. The canonical runner validates and stages one immutable application
candidate, including its dependency lock, mandatory tests, and harness controls,
then executes checks against that staged snapshot rather than the mutable
workspace.

## Technical Context

| Area | Plan |
|---|---|
| Language/version | Python 3.12 |
| Primary dependencies | FastAPI 0.162.4 and Pydantic 2.14.3; use Python standard-library facilities for JSON, paths, temporary files, replacement, synchronization, and hashing. |
| Development dependencies | pytest 9.2.0, HTTPX 0.28.1, Ruff 0.17.4, Bandit 1.9.4, and Uvicorn 0.54.0 for local serving. Resolved together with uv on CPython 3.12; commit `uv.lock` with the project configuration (D-04). |
| Storage | One local JSON document containing `next_id` and the task array. Factory `Path` override, then `SMART_TODO_STORE_PATH`, then `data/tasks.json`; runtime data is Git-ignored (D-02). |
| Testing | pytest with an in-process ASGI client; all acceptance tests run through the protected harness. Automated application tests make no external network requests. |
| Target platform | Windows-compatible Python 3.12; use `pathlib`, close file handles before replacement, and avoid POSIX-only assumptions. Use `os.replace` only as a best-effort replacement mechanism; the approved contract makes no Windows atomic-visibility or crash-durability guarantee. |
| Project type | Small HTTP API / web service |
| Performance goals | No throughput or latency target is specified. Prioritize correctness for a single local collection. |
| Constraints | Deterministic sequential behavior; single-process mutation serialization; no multi-process writer guarantee, external services, database, or unrequested features. D-05 is resolved by the approved application-level recovery amendment; D-01 remains the trusted-validation blocker. |
| Scale/scope | One local task collection, no pagination or multi-user ownership. Maximum collection size is not specified. |

## Constitution Check

| Principle | Plan alignment |
|---|---|
| I. Specification-First Development | The original plan/specification v1.3.0 approval is dated 2026-11-12; feature specification v1.4.0 and its D-05 amendment were approved 2026-11-13. D-01 remains a separate trusted-validation blocker. |
| II. Clean Architecture | Routes depend on the service; the service depends on domain rules and a repository boundary; persistence does not depend on API code. |
| III. Deterministic Behaviour | Sequential requests from identical persisted state produce identical results. Concurrent mutation serialization follows NFR-007; request-to-ID assignment is unspecified. |
| IV. API Contract Integrity | OpenAPI design mirrors the documented endpoints, status codes, response shapes, and error envelope. |
| V. Data Integrity | Lazy request-time validation and `MalformedStoredDataError` remain unchanged. Candidate bytes and a uniquely named same-directory backup are verified; best-effort replacement is followed by primary-byte verification before memory commit. Handled failures restore and verify prior bytes or absence; unverifiable recovery preserves material and fails closed. No Windows atomic-visibility or crash-durability guarantee is claimed. |
| VI. Security | No secrets or local environment files are committed; request validation and stable public errors are required. The final repository security review remains a human gate. |
| VII. Requirement-Driven Testing | [test-strategy.md](./test-strategy.md) maps all 29 acceptance criteria to mandatory test focuses. |
| VIII. Code Quality | Use type annotations and modular Python; the runner requires zero Ruff violations and captures Bandit execution status, exit code, stdout/stderr, and machine-readable findings. A human security reviewer records each finding's disposition and determines whether the review gate is satisfied. |
| IX. Independent Validation Harness | Part-1A includes required `.harness/` scripts/configuration and `tests/` as submitted, untrusted copies. The selected implementation is a GitHub Actions workflow dispatched from protected `main`; it verifies the human-approved control/test baseline, checks out an explicit candidate separately, uses read-only permission, supplies no secrets to candidate code, and verifies run-specific staging before and after execution. `.harness/instruction-files.json` explicitly inventories exact governing files and digests. A branch ruleset alone does not prove canonical runner independence; D-01 remains blocked until the workflow, approvals, execution boundary, and actual run are verified. |
| X. Traceability and Evidence | Part-1A includes `evidence/` organization. The runner generates local evidence copies and retains authoritative evidence in its protected store. |
| XI. Human Accountability | Automated results never choose ACCEPT/REJECT; a human security review and a separate explicit final decision are required. |

**Gate result**: The original approval and dependency/version checks recorded
for v1.3.0 remain historical. The D-05 guarantee change is explicitly approved
by the human on 2026-11-13 and is recorded in feature specification v1.4.0 and
research.md. D-05 no longer blocks the application implementation. D-01 remains
open: the protected runner boundary and authoritative execution have not been
established.

## Proposed Architecture

### Responsibilities

| Module | Responsibility and allowed dependencies |
|---|---|
| `smart_todo.app` | Expose `create_app(store_path: Path | None = None)`; wire one shared service/repository per app and install exception handlers that translate repository failures to the stable API envelope. An explicit `Path` wins over `SMART_TODO_STORE_PATH`, which wins over `data/tasks.json`. Resolve relative paths against the process working directory when creating the app; do not read the store during app construction. |
| `smart_todo.api.routes` | Define the six routes, path/query parsing, request dispatch, response models, `Location` header, and documented HTTP statuses. Call the service only. |
| `smart_todo.api.schemas` | Pydantic request/response types, strict unknown-field rejection, and API validation constraints. |
| `smart_todo.api.errors` | Convert request-validation, business, and repository failures into the common stable error envelope. Keep malformed JSON, malformed stored data, and persistence failures distinct without changing their public codes/statuses. |
| `smart_todo.domain.models` | Task fields, enums, domain invariants, and immutable/snapshot representations. |
| `smart_todo.domain.service` | CRUD, tag normalization/filtering, ordering, status transitions, ID allocation, and in-process mutation coordination. It uses an injected repository port and does not import the JSON repository or persistence exceptions. |
| `smart_todo.domain.ports` | Define the narrow repository protocol consumed by the service; the concrete JSON repository implements it. This dependency points inward and does not expose a concrete persistence implementation. |
| `smart_todo.domain.errors` | Task/business-rule errors only, such as not-found and invalid-transition. It contains no malformed-store or persistence exceptions. |
| `smart_todo.persistence.errors` | Define persistence-specific exceptions, including `MalformedStoredDataError` and local persistence failure, without depending on FastAPI or domain error definitions. |
| `smart_todo.persistence.json_repository` | Implement the domain repository port; perform lazy load, complete stored-document validation, deterministic serialization, temporary-file creation, and replacement. Raise typed persistence exceptions from `persistence.errors`; do not translate them to HTTP. |

### Request and State Flow

1. Application creation wires one shared service/repository instance into the
   app's dependency state; it does not open or validate the JSON file. This
   allows the process to start when the existing file is malformed.
2. The first request that accesses the repository loads and validates the whole
   document. A missing file creates an in-memory empty state with `next_id=1`;
   malformed JSON/shape raises `MalformedStoredDataError` and is not cached or
   repaired.
3. API routes validate the request and call the service. The service applies
   business rules and coordinates operations under one standard-library
   in-process lock. Synchronous route handlers are the simplest fit for the
   synchronous JSON repository; FastAPI dispatches them through its worker
   thread pool.
4. For a mutation, the service builds a candidate state, asks its injected
   repository port to persist it using the approved backup/recovery contract,
   and swaps the in-memory snapshot only after primary-byte verification.
   Repository-specific exceptions propagate unchanged through the service;
   the application/API boundary maps them to `malformed_stored_data` or
   `persistence_error` and retains the prior state.
5. Reads take a consistent snapshot under the same coordination boundary.
   Concurrent mutation results must be equivalent to some serial execution;
   which request receives each ID is intentionally not guaranteed.

The proposed synchronization primitive is `threading.Lock` owned by the service
or repository transaction boundary. It protects one process only, matching the
specification's explicit exclusion of independent process writers. Keep the
lock held over state read, candidate construction, file replacement, and
in-memory commit; do not expose mutable state outside that boundary.

The persistence transaction serializes candidate bytes before touching the
store; it creates and verifies a uniquely named same-directory backup for an
existing primary, writes and closes same-directory temporary files, and uses
`os.replace` as a best-effort replacement operation. It verifies the installed
primary bytes before publishing memory. A handled failure attempts byte-exact
restoration from the verified backup or restoration of original absence. Failed
verification preserves recovery material and puts the repository in a
fail-closed state. This contract does not claim Windows atomic visibility,
crash durability, recovery from abrupt process/OS failure, or hardware-level
persistence.

## Project Structure

```text
Part-1A/
├── .gitignore                 # excludes /data/, local env files, and .venv/
├── pyproject.toml
├── uv.lock                    # generated with uv; include in commits
├── .github/
│   └── skills/speckit-*/SKILL.md
├── .specify/
│   ├── .gitignore
│   ├── feature.json
│   ├── init-options.json
│   ├── integration.json
│   ├── integrations/*.manifest.json
│   ├── memory/constitution.md
│   ├── scripts/powershell/*.ps1
│   ├── templates/*template.md
│   └── workflows/
├── src/
│   └── smart_todo/
│       ├── app.py
│       ├── api/
│       │   ├── routes.py
│       │   ├── schemas.py
│       │   └── errors.py
│       ├── domain/
│       │   ├── models.py
│       │   ├── ports.py
│       │   ├── service.py
│       │   └── errors.py
│       └── persistence/
│           ├── errors.py
│           └── json_repository.py
├── tests/
│   ├── unit/
│   ├── api_contract/
│   ├── persistence/
│   ├── concurrency/
│   ├── error_handling/
│   └── harness_integrity/
├── .harness/
│   ├── run.ps1
│   ├── mandatory-checks.json
│   ├── instruction-files.json # exact approved instruction/governing file inventory
│   └── protected-files.manifest  # working copy; not authoritative
├── evidence/
│   ├── initial/
│   ├── final/
│   ├── results/
│   ├── failures/
│   ├── repairs/
│   ├── security-review/
│   └── human-decision/
├── data/                       # runtime only; ignored by Git
│   └── tasks.json              # default store; generated at runtime
└── specs/001-smart-todo-api/
    ├── plan.md
    ├── research.md
    ├── data-model.md
    ├── test-strategy.md
    ├── quickstart.md
    ├── checklists/requirements.md
    └── contracts/openapi.yaml

<trusted-runner-store>/  # separately access-controlled; not part of Part-1A
├── canonical-runner/
├── baseline/manifest.json
├── approvals/                 # protected human approval records/register
├── bootstrap/                 # out-of-band enrollment procedure and records
├── verified-staging/<run-id>/ # immutable snapshot used for execution
└── evidence/<run-id>/          # authoritative runner-generated evidence
```

The Part-1A `.harness/`, `tests/`, and `evidence/` directories are required
repository contents. Their submitted copies are untrusted candidates/evidence,
not trusted merely because they are outside `src/`, outside the VS Code
workspace, or outside the application package. Before execution, the canonical
runner verifies exact SHA-256 digests of the submitted runner, tests, expected
results, controls, `.harness/instruction-files.json`, and each inventoried file
against the separately protected baseline and approval records. It stages and
executes only the verified immutable snapshot. The inventory lists only actual
instruction/governing files that influence coding or validation. Each entry
uses the keys `path`, `purpose`, `classification`, `sha256`, and
`approval_reference`, with exact values; wildcard entries are prohibited. The
inventory and listed files are included in both the
validation candidate manifest and trusted baseline workflow. Runner-generated
results are mirrored into Part-1A while an authoritative copy remains in the
protected store.

The selected trust boundary uses GitHub's protected `main` branch and a
workflow dispatched from that branch. The workflow's definition and trusted
control scripts are checked out from `main`; the candidate commit is checked
out separately and is never used as the workflow definition. The job has
`contents: read`, does not expose secrets, verifies approved hashes, stages
candidate bytes in a unique run directory, checks integrity before and after
execution, and uploads complete logs and evidence. No additional Windows
account is required. The exact branch ruleset settings and runner isolation
still require human verification; a protected branch alone does not establish
canonical runner independence.

### Initial Trusted-Runner Bootstrap

D-01 remains unresolved until the human/assignment owner establishes and
verifies this GitHub trust boundary. Bootstrap must occur through the protected
main-branch review and approval process:

1. Verify the configured `main` branch ruleset and which actors can change the
   workflow, trust scripts, baseline, and approval register. Do not infer this
   from the protected-branch flag alone.
2. Independently review the initial workflow, trust scripts, mandatory tests,
   expected results, validation controls, `.harness/instruction-files.json`,
   the ten listed instruction files, and their exact SHA-256 digests.
3. Use the single `.harness/trust/approval-register.json` review record to
   record the actual reviewer, date, rationale, source commit, decision, and
   reference for the complete inventory. Do not fill blank fields or invent
   approval data.
4. Merge the reviewed workflow and baseline to protected `main` through its
   configured governance process. The workflow must fail closed while approval
   data is missing or hashes differ.
5. Dispatch the workflow from `main` with an explicit full candidate commit
   SHA. Confirm it runs the trusted workflow/control files from `main`, verifies
   the candidate before execution, and retains integrity-bound results.
6. Every later change to runner, tests, expected results, controls,
   `.harness/instruction-files.json`, or an inventoried instruction file
   requires a new human approval and protected baseline update. Test
   tamper-detection only against disposable fixtures; never alter an approved
   baseline without human approval.

The initial repository runner is not trusted because it computes or reports its
own hashes. Its digest is established by the human administrator and its first
authoritative invocation is mediated by the already protected canonical runner.

## Testing and Validation Architecture

See [test-strategy.md](./test-strategy.md) for the complete AT-001 through
AT-029 test matrix. Tests use unit, API contract, persistence, concurrency, and
error-handling groups. API tests use an in-process client; filesystem tests use
isolated temporary directories; concurrency tests use simultaneous requests in
one application instance. HT-001 and HT-002 are supplemental harness tests and
do not add or alter an acceptance criterion.

### Validation Candidate Manifest

The canonical runner first verifies the protected human approval register and
the SHA-256 baseline for the repository runner, mandatory tests, expected
results, validation controls, and `.harness/instruction-files.json`. It verifies
each exact path and digest in the inventory against that approved inventory and
protected baseline; wildcard or unlisted governing files are not admitted.
Before the authoritative run, it calculates
a sorted per-file SHA-256 **validation candidate manifest** and stages exactly
those verified bytes in a protected, run-specific immutable directory that the
coding-agent identity cannot modify. The manifest covers every file used for
validation: application source, tests, harness scripts/configuration, dependency
files, required project/test configuration, approved Spec Kit artifacts, and
only the exact instruction/governing files listed in the controlled inventory.
It includes at least `src/`, `.gitignore`, `pyproject.toml`, `uv.lock`, `tests/`,
`.harness/` including `instruction-files.json`, `specs/001-smart-todo-api/`, and
the exact inventoried files. It excludes generated evidence, runtime data,
virtual environments, caches, and other explicitly enumerated ephemeral files.
The protected runner stores the manifest and its digest outside the candidate.
Evidence generation therefore cannot change the validation candidate digest.

The runner provisions dependencies from the staged `pyproject.toml` and
`uv.lock`, sets the staged project root as the working directory, and runs all
mandatory pytest, Ruff, Bandit, architecture, repository-hygiene, and traceability
checks against the staged files. Python imports must resolve to the staged
`src/` package, never the mutable VS Code workspace. The runner verifies the
candidate manifest after staging and before and after execution. A
missing/invalid approval, baseline mismatch, staging mismatch, or mandatory
failure fails closed with a non-zero exit and runner-generated evidence.

### Evidence Bundle Manifest

A separate sorted per-file SHA-256 **evidence bundle manifest** covers
runner-generated results, logs, initial/final snapshot references, failure
evidence, repair history, and the subsequent human security-review and
human-decision records. The bundle records the exact validation candidate
manifest digest for each authoritative run, so initial failures and repaired or
final results remain attributable to their respective candidate snapshots. The
final human decision names the final validated candidate digest. The runner
calculates the evidence manifest after each evidence update and verifies bundle
integrity before publication; human records are added through the protected
approval workflow. Store both manifests as detached protected records, not as
members of the file sets they hash. Evidence additions or changes do not alter
any candidate manifest.

Before publication, verify both that the publication candidate's validation
manifest exactly matches the tested candidate manifest and that the evidence
bundle still matches its evidence manifest and references that same candidate
digest. Any mismatch rejects publication and, for candidate changes, requires
another complete validation run. Automated checks record results only. Human
security review, ACCEPT/REJECT, and publication gates remain separate.

After final automated validation, the human security review is added to the
evidence bundle and its manifest is refreshed. The human decision references
the validated candidate digest and the then-current evidence manifest digest
(which includes the final results and security review, but not the decision
record itself). After the human decision is recorded, regenerate the detached
final evidence bundle manifest to cover that decision record and verify the
completed bundle before publication; this avoids a self-referential manifest
while retaining integrity for both the decision input and the final record.

The runner owns evidence capture: preserve the initial implementation snapshot
before repair, final snapshot reference, tool versions and commands, structured
initial/final results, stdout/stderr, failed checks, each repair and its
revalidation, and references to the human security review and decision.
Part-1A `evidence/` contains generated copies; the runner's protected evidence
store is authoritative. Runner-generated results must not be manually edited.

## Open Technical Decisions for Human Review

| ID | Status / decision | Proposed boundary / impact |
|---|---|---|
| D-01 | **Design direction closed; implementation blocker remains** | GitHub-based governance and protected `main` were selected; the human reports that the main ruleset is configured. Part-1A's workflow and consolidated approval-register template are candidate files only. The human/assignment owner must review and approve the exact workflow, tests, controls, instruction inventory and ten inventoried files, verify who can administer the boundary, merge the approved baseline to `main`, and run the workflow with an explicit candidate SHA. A branch ruleset alone does not establish canonical runner independence; D-01 remains blocked until the protected workflow and actual run are verified. No additional Windows account is required. |
| D-02 | **Resolved for planning** | `create_app(store_path: Path | None = None)` explicit path takes precedence; otherwise use non-empty `SMART_TODO_STORE_PATH`; if absent, default to `data/tasks.json` relative to the process working directory. Resolve path at app creation; do not load store then. `.gitignore` excludes `/data/`; any custom path must also be outside tracked files or ignored. |
| D-03 | **Resolved by approved specification v1.3.0 (2026-11-12)** | The approved v1.3.0 specification includes the error-details schema (exact string fields `field`, `code`, and `message`; `details: []` without field-level information; deterministic ordering), harness-copy trust boundaries, Bandit human disposition, and controlled instruction-file inventory. |
| D-04 | **Resolved for planning; commit gate remains** | `pyproject.toml` and `uv.lock` are generated in Part-1A using uv; include both in project commits. The Windows CPython 3.12 resolution selected FastAPI 0.162.4, Pydantic 2.14.3, pytest 9.2.0, HTTPX 0.28.1, Ruff 0.17.4, Bandit 1.9.4, and Uvicorn 0.54.0. Review the dependency/lock diff before implementation; see `research.md`. |
| D-05 | **Resolved by approved specification v1.4.0 (2026-11-13)** | The human-approved amendment retains JSON and replaces the unsupported Windows atomic-visibility/crash-durability guarantee with application-handled backup, byte-verification, restoration, and fail-closed behavior. `os.replace` remains best effort only. No OS-level atomic visibility, crash durability, abrupt process/OS recovery, or hardware persistence guarantee is claimed. |

The feature's scope, status transitions, priority/tag semantics, stored JSON
shape, error codes, sequential determinism, single-process serialization,
failure rollback, and human acceptance gates are otherwise specified. The plan
adds no application functionality; implementation sequencing is tracked
separately in `tasks.md`.

## Complexity Tracking

No unnecessary subsystems or waived constitution requirements are proposed. The
API, service, model, and repository boundaries are required by the specification.
The required repository harness and evidence structure coexist with a genuinely
separate trusted runner boundary. D-01 remains an authoritative validation gate;
D-05 is resolved by the approved v1.4.0 application-level recovery contract.
