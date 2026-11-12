# Implementation Plan: Smart Todo & Task Management API

**Branch**: `001-smart-todo-api` | **Date**: 2026-11-11 | **Spec**:
[spec.md](./spec.md)

**Status**: ACCEPT

**Approved**: 2026-11-12

**Planning basis**: Constitution v1.1.0, feature specification v1.3.0, and this
implementation plan have human approval dated 2026-11-12. The approved plan and
research record the dependency versions below. D-01 and D-05 remain independent
open technical blockers and are not resolved by artifact approval.

## Summary

Build a small, single-process FastAPI service with explicit Pydantic request,
response, domain, and stored-document models. A business service owns task rules
and mutation coordination. A JSON repository lazily reads and fully validates
the configured local document, then persists complete candidates through a
same-directory temporary file and replacement. In-memory state advances only
after persistence succeeds. Part-1A contains the required `src/`, `tests/`,
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
| Target platform | Windows-compatible Python 3.12; use `pathlib`, close file handles before replacement, and avoid POSIX-only assumptions. Formal atomic-replacement behavior on the supported Windows filesystem must be resolved (D-05). |
| Project type | Small HTTP API / web service |
| Performance goals | No throughput or latency target is specified. Prioritize correctness for a single local collection. |
| Constraints | Deterministic sequential behavior; single-process mutation serialization; no multi-process writer guarantee, external services, database, or unrequested features. Preserve the specified atomic-replacement requirement; its Windows guarantee remains unresolved (D-05). |
| Scale/scope | One local task collection, no pagination or multi-user ownership. Maximum collection size is not specified. |

## Constitution Check

| Principle | Plan alignment |
|---|---|
| I. Specification-First Development | This plan follows the human-approved constitution v1.1.0 and feature specification v1.3.0, both approved on 2026-11-12. The approved planning set records the dependency versions below. D-01 and D-05 remain separate technical blockers. |
| II. Clean Architecture | Routes depend on the service; the service depends on domain rules and a repository boundary; persistence does not depend on API code. |
| III. Deterministic Behaviour | Sequential requests from identical persisted state produce identical results. Concurrent mutation serialization follows NFR-007; request-to-ID assignment is unspecified. |
| IV. API Contract Integrity | OpenAPI design mirrors the documented endpoints, status codes, response shapes, and error envelope. |
| V. Data Integrity | Lazy request-time validation, `MalformedStoredDataError`, candidate-state writes, same-directory temporary files, and replacement-before-memory-commit follow the specification. Windows atomic-visibility assurance is an open platform gate (D-05). |
| VI. Security | No secrets or local environment files are committed; request validation and stable public errors are required. The final repository security review remains a human gate. |
| VII. Requirement-Driven Testing | [test-strategy.md](./test-strategy.md) maps all 29 acceptance criteria to mandatory test focuses. |
| VIII. Code Quality | Use type annotations and modular Python; the runner requires zero Ruff violations and captures Bandit execution status, exit code, stdout/stderr, and machine-readable findings. A human security reviewer records each finding's disposition and determines whether the review gate is satisfied. |
| IX. Independent Validation Harness | Part-1A includes required `.harness/` scripts/configuration and `tests/` as submitted, untrusted copies; the canonical runner, protected test/control baseline, approval records, and execution environment are separately protected. `.harness/instruction-files.json` explicitly inventories exact governing files and digests. Repository location alone is not a security boundary; D-01 remains blocked unless the separate identity/ACL or protected CI boundary is demonstrated. |
| X. Traceability and Evidence | Part-1A includes `evidence/` organization. The runner generates local evidence copies and retains authoritative evidence in its protected store. |
| XI. Human Accountability | Automated results never choose ACCEPT/REJECT; a human security review and a separate explicit final decision are required. |

**Gate result**: Human approval of constitution v1.1.0, feature specification
v1.3.0, and this plan was recorded on 2026-11-12. The artifact, specification
version, error-details, and dependency-version approval checks in T003 are
satisfied. This does not assert that approval preceded implementation, and it
does not resolve D-01 or D-05: the protected runner boundary and Windows
atomic-visibility requirement remain open implementation blockers.

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
   repository port to persist it atomically, and swaps the in-memory snapshot
   only after replacement succeeds. Repository-specific exceptions propagate
   unchanged through the service; the application/API boundary maps them to
   `malformed_stored_data` or `persistence_error` and retains the prior state.
5. Reads take a consistent snapshot under the same coordination boundary.
   Concurrent mutation results must be equivalent to some serial execution;
   which request receives each ID is intentionally not guaranteed.

The proposed synchronization primitive is `threading.Lock` owned by the service
or repository transaction boundary. It protects one process only, matching the
specification's explicit exclusion of independent process writers. Keep the
lock held over state read, candidate construction, file replacement, and
in-memory commit; do not expose mutable state outside that boundary.

The proposed replacement uses a same-directory temporary file, closes all
handles, and then invokes a Windows replacement mechanism. Neither Python's
`os.replace` documentation nor the reviewed Win32 `ReplaceFileW` and
`MoveFileExW` documentation establishes the required Windows atomic-visibility
guarantee. `ReplaceFileW` also documents failure outcomes in which the original
may no longer remain at its original path. Therefore D-05 remains an
implementation blocker; do not weaken the approved data-integrity requirement.

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

The canonical runner, baseline, approval records, staging area, and authoritative
evidence must be writable only by a separately administered Windows identity or
protected CI service. The coding agent's identity must lack write/admin access.
ACLs/CI permissions—not directory location or Git history—enforce the boundary.
If the agent can act as the trusted identity, administer the host, or change the
CI policy, the mechanism is defeated; D-01 remains blocked until an actual
separation is demonstrated. A same-user local setup cannot claim this protection.

### Initial Trusted-Runner Bootstrap

D-01 remains unresolved until the human/assignment owner establishes and
verifies this separate trust boundary. Bootstrap must occur out of band from the
repository runner:

1. Establish the separate Windows identity/ACL or protected CI environment and
   the protected canonical-runner, baseline, approval, staging, and evidence
   stores. The coding-agent identity must not be able to administer them.
2. Create the initial Part-1A repository runner, mandatory tests, expected
   results, validation controls, `.harness/instruction-files.json`, and the
   exact instruction files it lists as untrusted candidate files.
3. A human administrator independently reviews those exact candidate files,
   verifies that the inventory contains only actual applicable files and no
   wildcard entries, and calculates their SHA-256 digests. The administrator
   records the source commit and verifies the candidate file set and digests
   before enrollment.
4. Through the protected out-of-band channel, enroll the approved file digests
   and initial baseline. Record the initial approver, actual approval date,
   rationale, source commit, and approved digests in the protected approval
   register. Do not invent missing metadata.
5. The first authoritative run invokes the canonical runner from the protected
   trust store. That runner verifies the repository runner and controls against
   the enrolled baseline, then stages and executes only the verified bytes.
   Never bootstrap by executing an unverified repository copy.
6. Every later change to runner, tests, expected results, controls,
   `.harness/instruction-files.json`, or an inventoried instruction file
   requires a new human approval record with exact old/new digests, followed by
   a protected baseline update. Test bootstrap and tamper detection only against
   disposable fixtures; never mutate the real canonical baseline.

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
| D-01 | **Open implementation blocker** | Part-1A must contain `.harness/`, `tests/`, and `evidence/` as submitted, untrusted repository copies. The human/assignment owner must establish and verify a separately administered Windows identity/ACL or protected CI, then independently review and enroll the canonical runner, tests, controls, `.harness/instruction-files.json`, inventoried files, and their exact digests through an out-of-band approval register. The first authoritative invocation starts from the canonical protected runner; only verified immutable snapshots execute. Location alone is not protection. If the separate identity/ACL or protected CI boundary cannot be demonstrated, D-01 remains blocked. |
| D-02 | **Resolved for planning** | `create_app(store_path: Path | None = None)` explicit path takes precedence; otherwise use non-empty `SMART_TODO_STORE_PATH`; if absent, default to `data/tasks.json` relative to the process working directory. Resolve path at app creation; do not load store then. `.gitignore` excludes `/data/`; any custom path must also be outside tracked files or ignored. |
| D-03 | **Resolved by approved specification v1.3.0 (2026-11-12)** | The approved v1.3.0 specification includes the error-details schema (exact string fields `field`, `code`, and `message`; `details: []` without field-level information; deterministic ordering), harness-copy trust boundaries, Bandit human disposition, and controlled instruction-file inventory. |
| D-04 | **Resolved for planning; commit gate remains** | `pyproject.toml` and `uv.lock` are generated in Part-1A using uv; include both in project commits. The Windows CPython 3.12 resolution selected FastAPI 0.162.4, Pydantic 2.14.3, pytest 9.2.0, HTTPX 0.28.1, Ruff 0.17.4, Bandit 1.9.4, and Uvicorn 0.54.0. Review the dependency/lock diff before implementation; see `research.md`. |
| D-05 | **Open implementation blocker** | `os.replace` has no documented Windows atomic-visibility guarantee. `ReplaceFileW` and `MoveFileExW` are possible Windows APIs, but reviewed Microsoft documentation does not establish the required guarantee; `ReplaceFileW` documents failure states that can leave the replaced file moved/missing. Do not claim atomic visibility or crash durability. Preserve the existing requirement and block implementation until a compliant supported approach is verified or a human explicitly amends the specification. |

The feature's scope, status transitions, priority/tag semantics, stored JSON
shape, error codes, sequential determinism, single-process serialization,
failure rollback, and human acceptance gates are otherwise specified. The plan
adds no application functionality; implementation sequencing is tracked
separately in `tasks.md`.

## Complexity Tracking

No unnecessary subsystems or waived constitution requirements are proposed. The
API, service, model, and repository boundaries are required by the specification.
The required repository harness and evidence structure coexist with a genuinely
separate trusted runner boundary. D-01 and D-05 remain implementation gates.
