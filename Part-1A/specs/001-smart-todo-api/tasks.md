# Tasks: Smart Todo & Task Management API

**Input**: Design documents in `specs/001-smart-todo-api/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`,
`test-strategy.md`, and `contracts/openapi.yaml`.

**Planning basis**: Human approval was recorded on 2026-11-12 for constitution
v1.1.0, feature specification v1.3.0, and the implementation plan. The approved
plan/research record contains the exact dependency versions, and approved
specification v1.3.0 establishes the error-details schema; T003 is complete.
The human-approved v1.4.0 specification amendment and constitution v2.0.0
amendment on 2026-11-13 resolve D-05 by replacing the unsupported Windows
atomic-visibility/crash-durability guarantee with the application-level recovery
contract. D-01 remains an explicit trust-boundary and authoritative-validation
gate. The owner later waived only the custom-bootstrap portions of AC-023 and
AC-024. Active AC-022 protected execution remains NOT VERIFIED; the waiver does
not create approval metadata or make local validation authoritative.

**Tests**: Required. Every acceptance criterion AC-001 through AC-029 maps to
the corresponding AT-001 through AT-029 test in `test-strategy.md`. Test changes
must use the human-approved baseline workflow; do not modify the trusted
baseline or approval records directly. HT-001 and HT-002 are supplemental
harness tests and do not add or change a specification acceptance criterion.

**Task count**: 45 tasks, T001-T045.

**Organization**: Setup, foundational gates, then user stories in priority and
dependency order. User Story 4 (persistence, P1) precedes User Story 1 (CRUD,
P1) because CRUD depends on the store. User Stories 2 and 3 are P2.

**Status notation**: A task whose description starts with `BLOCKED` must not be
started until its named decision/dependency is resolved and verified.

## Phase 1: Setup

**Purpose**: Confirm dependency configuration and create the required assignment
project structure without adding application behavior. T002 may proceed
independently. T003 approval is recorded, and T001 dependency configuration and
lockfile verification are complete.

- [x] T001 Create or complete `pyproject.toml` only after T003 verifies actual human approval of the project and the exact package-version set: FastAPI 0.162.4, Pydantic 2.14.3, pytest 9.2.0, HTTPX 0.28.1, Ruff 0.17.4, Bandit 1.9.4, and Uvicorn 0.54.0. Generate `uv.lock`, verify the active interpreter and dependency resolution target Python 3.12, then run `uv lock --check --python 3.12` and `uv sync --locked`. Record the approved dependencies in `pyproject.toml`, `uv.lock`, and `specs/001-smart-todo-api/research.md`. Before T003 was completed, only read-only environment inspection (for example, `python --version` and `uv --version`) was permitted; do not create or modify either project file or install project dependencies.
- [x] T002 [P] Create the planned `src/`, `tests/`, `.harness/`, and `evidence/` directory structure from `plan.md`; preserve runtime-data and local-environment exclusions in `.gitignore`.

## Phase 2: Foundational Gates

**Purpose**: Resolve governance and trust prerequisites before any user-story
implementation or authoritative test execution.

- [x] T003 Verify the human approval recorded on 2026-11-12 for constitution v1.1.0, feature specification v1.3.0, and the implementation plan. Confirm the plan/research dependency set (FastAPI 0.162.4, Pydantic 2.14.3, pytest 9.2.0, HTTPX 0.28.1, Ruff 0.17.4, Bandit 1.9.4, and Uvicorn 0.54.0) and the approved v1.3.0 error-details schema. This records the user's explicit approval in this interaction; it is not a protected approval-register reference. D-01's AC-023/AC-024 custom-bootstrap portions were later waived; active AC-022 protected execution remains unverified. D-05 was later resolved by the separately approved v1.4.0 amendment dated 2026-11-13.
- [ ] T004 [P] NOT VERIFIED (active AC-022): Verify the configured GitHub `main` ruleset and which actors can administer the workflow, staging, and evidence. Do not create Windows accounts. Verify the trusted workflow runs from protected `main`, uses a read-only token, provides no secrets to candidate code, and cannot be bypassed by selecting a candidate-controlled workflow definition. The owner waiver applies only to custom-bootstrap portions of AC-023/AC-024 and does not waive these independent execution-boundary checks.
- [x] T005 [P] Resolve D-05 by applying the explicitly human-approved 2026-11-13 amendment to feature specification v1.4.0 and Constitution v2.0.0. Retain JSON persistence; replace the unsupported Windows atomic-visibility/crash-durability guarantee with the application-level backup, byte-verification, restoration, and fail-closed contract. Update `research.md`, `plan.md`, AC-014/test strategy, and related harness checks. Do not claim that `os.replace`, `ReplaceFileW`, `MoveFileExW`, or local tests establish Windows atomic visibility or crash durability. D-01 remains independently blocked.
- [x] T006 Verify `specs/001-smart-todo-api/contracts/openapi.yaml` against the human-approved `specs/001-smart-todo-api/spec.md`; confirm the approved error-details schema and every documented endpoint/status-code set, including existing error contracts. Correct the OpenAPI contract only to match the actually approved specification; if approval or the error-details amendment is unresolved, stop without treating a proposal as approved.
- [x] T007 (T003-T006): Create the architecture scaffolding and application factory in `src/smart_todo/app.py`, `src/smart_todo/api/`, `src/smart_todo/domain/`, and `src/smart_todo/persistence/`; define the repository port separately from its JSON implementation and install application/API error translation; accept an explicit `Path`, otherwise use `SMART_TODO_STORE_PATH`, then `data/tasks.json`, without loading the store during app creation. Architecture tests pass locally; authoritative validation remains blocked by D-01.

## Phase 3: User Story 4 - Keep Tasks Across Restarts (Priority: P1)

**Goal**: Persist and validate the JSON collection without losing valid data or
silently resetting malformed data.

**Independent Test**: Against an isolated store, restart and verify tasks and
`next_id`; inject malformed stored documents and persistence failures and verify
the specified error and preservation behavior.

### Tests for User Story 4

- [x] T008 [US4] Add and locally validate AT-013, revised AT-014 recovery cases, and AT-015 in `tests/persistence/test_json_repository.py`; cover restart persistence, full candidate serialization, verified backup, candidate/backup/replacement/recovery/cleanup failures, byte-exact restoration or verified absence, unchanged memory, fail-closed behavior, and request-time malformed-store errors with unchanged source bytes. This completes local candidate test work only; D-01 authoritative execution remains blocked.
- [x] T009 [US4] Add AT-029 concurrency tests in `tests/concurrency/test_concurrent_mutations.py`; verify serializable results, unique sequential IDs, no lost updates, persisted `next_id` and next ID after restart, failed-write rollback, and no assertion about request-to-ID ordering. Local candidate coverage passes; authoritative execution remains blocked by D-01.

### Implementation for User Story 4

- [x] T010 [US4] Implement strict task and stored-document models in `src/smart_todo/domain/models.py`; enforce positive integer IDs (reject Booleans), trimmed 1-200 character titles, null or 0-2000 character descriptions, at most 20 distinct trimmed lowercase 1-32 character tags in lexicographic order, priorities `Low`/`Medium`/`High`, and statuses `Pending`/`In Progress`/`Completed`. Existing implementation and local tests pass; authoritative validation remains blocked by D-01.
- [x] T011 [US4] Implement lazy JSON loading and complete validation in `src/smart_todo/persistence/json_repository.py`; require exactly root fields `next_id` and `tasks`, exactly the six task fields, unique IDs, `next_id` greater than every ID, duplicate-member detection, and request-time `MalformedStoredDataError` from `src/smart_todo/persistence/errors.py` without resetting or overwriting the store. Keep domain errors business-only; propagate repository exceptions without making the domain depend on JSON persistence. Existing implementation and local tests pass; authoritative validation remains blocked by D-01.
- [x] T012 [US4] Implement the approved application-level JSON transaction in `src/smart_todo/persistence/json_repository.py`: serialize before touching the primary; create and verify unique same-directory backup/temp files; use best-effort `os.replace`; verify primary bytes before return; restore exact prior bytes or absence on handled failure; preserve recovery material and fail closed when restoration cannot be verified; and avoid invalidating a verified commit on cleanup failure. D-01 trusted validation remains separate.
- [x] T013 [US4] Serialize each instance's mutations and reads through the agreed synchronization boundary in `src/smart_todo/domain/service.py`; keep candidate state separate until persistence succeeds and ensure outcomes correspond to a serial execution. Existing concurrency tests pass locally; authoritative validation remains blocked by D-01.

## Phase 4: User Story 1 - Manage Tasks (Priority: P1)

**Goal**: Provide task creation, retrieval, listing, partial updates, and deletion
with deterministic identifiers and the documented API contract.

**Independent Test**: Complete create/read/update/list/delete against an
isolated store and verify IDs, representations, response codes, validation, and
error envelopes.

### Tests for User Story 1

- [x] T014 [US1] Add AT-001, AT-003, AT-004, AT-005, AT-016, and AT-019 API contract tests in `tests/api_contract/test_task_crud.py`, `tests/error_handling/test_request_validation.py`, and `tests/api_contract/test_endpoint_contract.py`; verify task lifecycle responses, `Location`, partial-update preservation, deletion, field boundaries, and all documented endpoint statuses. Local tests pass; authoritative validation remains blocked by D-01.
- [x] T015 [US1] Add AT-002 ID-allocation tests in `tests/unit/test_id_allocation.py`; verify IDs start at 1, increment for successful creates, remain deterministic from identical state, and are not reused after deletion or restart. Local tests pass; authoritative validation remains blocked by D-01.
- [x] T016 [US1] Add AT-018 and AT-020 error-contract tests in `tests/error_handling/test_request_validation.py`; cover malformed JSON, invalid IDs/query/body/fields/enums, exact error envelopes, exactly string fields `field`, `code`, `message`, empty `details` when no field information applies, deterministic ordering, and no internal details. Local tests pass; authoritative validation remains blocked by D-01.

### Implementation for User Story 1

- [x] T017 [US1] Implement deterministic CRUD and ID allocation in `src/smart_todo/domain/service.py`; allocate from persisted `next_id` and increment only for a successfully persisted creation. Existing implementation and local tests pass; authoritative validation remains blocked by D-01.
- [x] T018 [US1] Implement explicit create/update request and task response schemas in `src/smart_todo/api/schemas.py`; reject unknown fields and enforce the approved title/description bounds and null/partial-update semantics. Existing implementation and local tests pass; authoritative validation remains blocked by D-01.
- [x] T019 [US1] Implement `POST /tasks`, `GET /tasks`, `GET /tasks/{id}`, `PATCH /tasks/{id}`, and `DELETE /tasks/{id}` in `src/smart_todo/api/routes.py`, preserving the OpenAPI contract and response codes. Existing implementation and local tests pass; authoritative validation remains blocked by D-01.
- [x] T020 [US1] Implement common error translation in `src/smart_todo/api/errors.py` and application exception wiring in `src/smart_todo/app.py`; keep `src/smart_todo/domain/errors.py` limited to task/business errors, define repository errors in `src/smart_todo/persistence/errors.py`, and translate them at the application/API boundary while preserving `invalid_json`, `not_found`, `validation_error`, `malformed_stored_data`, and `persistence_error` envelopes and statuses. Existing implementation and local tests pass; authoritative validation remains blocked by D-01.

## Phase 5: User Story 2 - Organize and Find Tasks (Priority: P2)

**Goal**: Normalize tags, filter by all requested tags, and sort priorities
deterministically.

**Independent Test**: Create tasks with overlapping tags and all priorities;
verify normalization, AND filtering, empty matches, priority order, and ID ties.

### Tests for User Story 2

- [x] T021 [US2] Add AT-006, AT-007, AT-008, AT-009, and AT-017 tests in `tests/api_contract/test_task_queries.py` and `tests/error_handling/test_request_validation.py`; cover tag normalization/count/type/length, AND multi-tag filters, zero matches, priority values/default, priority sorting, and deterministic ties. Local tests pass; authoritative validation remains blocked by D-01.

### Implementation for User Story 2

- [x] T022 [US2] Implement tag normalization, deduplication, AND filtering, priority sorting, and ID-ascending tie/default order in `src/smart_todo/domain/service.py`. Existing implementation and local tests pass; authoritative validation remains blocked by D-01.
- [x] T023 [US2] Implement repeated `tag` and `sort=priority` query parsing and validation in `src/smart_todo/api/schemas.py` and `src/smart_todo/api/routes.py`; return `200`, `items: []`, and `count: 0` for no matches. Existing implementation and local tests pass; authoritative validation remains blocked by D-01.

## Phase 6: User Story 3 - Track Task Progress (Priority: P2)

**Goal**: Support only permitted status transitions and preserve task state on
rejection.

**Independent Test**: Exercise every allowed, idempotent, and prohibited
transition and verify response codes and stored status.

### Tests for User Story 3

- [x] T024 [US3] Add AT-010, AT-011, and AT-012 tests in `tests/api_contract/test_status_transitions.py`; cover the `Pending` default, both permitted transitions, same-status no-op, every prohibited transition, and unchanged state on `409`. Local tests pass; authoritative validation remains blocked by D-01.

### Implementation for User Story 3

- [x] T025 [US3] Implement lifecycle rules in `src/smart_todo/domain/service.py`; permit only `Pending -> In Progress` and `In Progress -> Completed`, make current-status requests no-ops, and reject every other transition without mutation. Existing implementation and local tests pass; authoritative validation remains blocked by D-01.
- [x] T026 [US3] Implement `PATCH /tasks/{id}/status` and its request schema in `src/smart_todo/api/routes.py` and `src/smart_todo/api/schemas.py`; preserve `400`, `404`, `409`, `422`, and `500` contracts. Existing implementation and local tests pass; authoritative validation remains blocked by D-01.

## Phase 7: Polish and Cross-Cutting Validation

**Purpose**: Complete cross-story determinism, harness protection, security,
quality gates, and attributable evidence.

- [x] T027 Add AT-021 sequential determinism tests in `tests/api_contract/test_determinism.py`; compare status, data, IDs, and ordering for identical request sequences and initial persisted state. Local tests pass; authoritative validation remains blocked by D-01.
- [x] T028 Implement the local harness as an untrusted repository candidate and add the protected-main GitHub Actions workflow plus bootstrap files. The workflow checks out trusted `main` separately from an explicit candidate SHA, uses read-only permission without candidate secrets, verifies approved digests, stages run-specific bytes, checks integrity before and after execution, and retains artifacts. The owner waived only the AC-023/AC-024 custom-bootstrap portions; the workflow remains a candidate and its protected execution is NOT VERIFIED.
- [ ] T029 NOT VERIFIED (active AC-022): Complete and verify zero Ruff findings, all tests, full AC mapping, Bandit output, network isolation, staging integrity, evidence-manifest integrity, publication equality, and non-human automated results. Local candidate checks are runnable, but the protected workflow run, independent execution boundary, hosted network isolation, and protected artifact verification remain unverified. The custom-bootstrap waiver does not waive these independent requirements.
- [x] T030 Add AT-023 disposable-baseline tamper tests in `tests/harness_integrity/test_github_trust_bootstrap.py`; verify approved control, inventory, instruction, governing specification, dependency, and test digests; reject unapproved changes before staging; and verify run-specific staged bytes against their manifest. These are local candidate tests, not canonical-runner enrollment.
- [x] T031 Add AT-024 inventory and synthetic approval tests in `tests/harness_integrity/test_github_trust_bootstrap.py`; verify the 19-file governing instruction and specification inventory, exact current digests, blank real approval references, and a synthetic approved disposable baseline. The actual protected approval-register portion is owner-waived; no real approval data is created.
- [x] T032 Add AT-025 architecture/runtime checks in `tests/harness_integrity/test_architecture.py`; verify Python 3.12, FastAPI/Pydantic use, route/service/persistence boundaries, service dependence on an abstract repository port, no domain import of the concrete JSON repository or persistence errors, and API-boundary translation of persistence exceptions. Local candidate tests pass; authoritative validation remains blocked by D-01.
- [x] T033 Add AT-026 repository-hygiene checks and synthetic fixtures in `tests/harness_integrity/test_repository_hygiene.py`; detect local environment files, credentials, and private keys and block publication on findings while excluding only preserved synthetic scanner fixture artifacts from historical evidence. Local scan verifies the publication candidate has zero findings; authoritative publication remains blocked by D-01.
- [x] T034 Add AT-027 human security-review gate tests in `tests/harness_integrity/test_security_review_gate.py` and `tests/harness_integrity/test_runner_boundaries.py`; verify exact Bandit finding identity matching, Bandit report SHA-256 binding, resolution or documented disposition and rationale, repository scope, reviewer identity/date, and human determination that the gate is satisfied. Automated gate behavior is locally tested; the actual human security review record under `evidence/security-review/` remains NOT VERIFIED for T044.
- [x] T035 Add AT-028 human decision-gate checks in `tests/harness_integrity/test_human_decision.py` and `tests/harness_integrity/test_runner_boundaries.py`; verify independent reconstruction of the pre-decision evidence bundle digest from disk (excluding `human-decision/decision.json`), rejection of pre-decision file tampering/missing/unexpected files, and enforcement that only a human-recorded `ACCEPT` opens publication while `REJECT` or no decision blocks it. Automated gate behavior is locally tested; the actual human final decision record under `evidence/human-decision/` remains NOT VERIFIED for T045.
- [x] T036 Add HT-001 staging-isolation and HT-002 manifest-separation/publication-gate coverage in `tests/harness_integrity/test_github_trust_bootstrap.py`; stage a disposable candidate, mutate its source afterward, verify the staged snapshot remains unchanged, detect staged-byte tampering, and verify separate evidence-manifest and publication-gate checks. It is not authoritative until D-01 enrollment and protected execution.
- [x] T037 WAIVED (owner direction scoped to AC-023/AC-024 custom bootstrap): No custom bootstrap baseline review or approval-register enrollment is required. This waiver does not constitute a review, create approval metadata, or waive AC-022 protected execution.
- [ ] T038 PARTIALLY WAIVED / NOT VERIFIED: The custom-bootstrap baseline and approval-register enrollment portion is waived by the owner. The active AC-022 requirement to verify protected workflow execution from `main`, fail-closed behavior, and an actual protected run remains NOT VERIFIED; do not infer it from local tests.
- [ ] T039 NOT VERIFIED (active AC-022, T028, T038): Verify the workflow artifact evidence layout and protected retention. Each run must bind the sorted candidate manifest to the candidate SHA, exclude evidence/runtime/cache data from candidate digesting, retain complete command logs and results, and provide a separately sealed evidence manifest. Verify the workflow artifact and publication-candidate equality before publication; evidence generation must not alter the candidate digest.
- [x] T040 Supporting documentation and deployment verification only (not a functional requirement or acceptance criterion): update `specs/001-smart-todo-api/quickstart.md` to the implemented API, actual Windows PowerShell/uv commands, local diagnostic limitation, and protected-main workflow path. Local commands and protected workflow remain distinct.
- [ ] T041 NOT VERIFIED (active AC-022, T001-T040): The custom-bootstrap trust-store prerequisite is waived, but the required protected canonical run is not verified. Do not substitute local diagnostics for the authoritative run. Preserve the first generated application snapshot and capture genuine protected-run candidate manifest, commands, versions, outputs, failures, evaluation record, and evidence manifest if/when that run is performed.
- [ ] T042 NOT VERIFIED (T041): Consume T041's genuine protected-run initial evidence. For each actual failure, record the failed check, mapped requirement, expected behaviour, observed behaviour, and stdout/stderr. Repair application behavior only when that evidence shows the application is at fault, without weakening approved requirements, tests, or harness, and preserve each repair and its evidence. If the harness, tests, controls, or cause is in question, stop for the required human review/approval rather than changing them. If there are no application failures, record that no repair was required. Re-run the exact same mandatory controls against the resulting staged candidate, calculating a new validation candidate manifest if any candidate file changed; preserve every run's results and candidate-digest reference in the evidence bundle and regenerate its integrity manifest. The earlier local diagnostic is not a substitute for T041 evidence.
- [ ] T043 NOT VERIFIED (active AC-022, T038, T042): Run final trusted automated validation through the canonical runner; require all mandatory tests to pass, Ruff to report zero violations, and Bandit to execute while preserving exit code, stdout, stderr, machine-readable findings, and execution status. Verify repository hygiene, candidate-manifest equality, evidence-bundle integrity, and that automated results contain no human disposition or ACCEPT/REJECT. Record final results and candidate digest.
- [x] T044 COMPLETE FOR THE REVIEWED LOCAL CANDIDATE (human action): The human reviewed the final preserved Bandit and repository-hygiene evidence. Bandit has zero findings and repository hygiene has zero findings. The exact reviewed candidate digest, reviewer identity, date, scope, disposition, and satisfied gate are recorded in `evidence/security-review/review.json`. Protected T043 execution remains NOT VERIFIED.
- [x] T045 COMPLETE FOR THE REVIEWED LOCAL CANDIDATE (human action): On 2026-11-21, `Shishir98` recorded explicit `ACCEPT` in `evidence/human-decision/decision.json`, with rationale and review date. The exact candidate digest is recorded in that decision evidence. This human decision applies to the assignment submission, not protected-run authority. T043 protected final validation, publication-candidate equality, and the protected evidence manifest remain NOT VERIFIED until performed through protected `main`.

## Dependencies and Execution Order

### Phase Dependencies

- **Phase 1**: T002 may proceed independently. T001 is blocked by T003 and
  must not create/modify `pyproject.toml` or `uv.lock`, or install dependencies,
  before human approval is verified.
- **Phase 2**: T003 is a human governance gate. T005 is complete through the
  approved v1.4.0 amendment. T004 remains NOT VERIFIED for active protected
  execution. T001 depends on T003; T006 depends on T003; T007 depends on T003-T006.
- **User Story 4 (P1)**: Depends on T003-T007; no persistence implementation
  or local test task remains blocked by D-05. Authoritative validation remains
  blocked by D-01.
- **User Story 1 (P1)**: Depends on the persistence layer in User Story 4.
- **User Stories 2 and 3 (P2)**: Depend on the core task/service/API layers.
- **Polish**: Depends on all story work and the protected GitHub workflow.
  Complete T040 quickstart documentation/deployment verification before freezing the
  candidate; then execute T041 initial validation, T042 repair/revalidation if
  needed, T043 final automated validation, T044 actual human security review,
  and T045 actual human ACCEPT/REJECT decision in that order.

### Blocking Decision Dependencies

- **D-01**: The owner waived only the custom-bootstrap portions of AC-023 and
  AC-024. T037 is waived, and the baseline/approval-register part of T038 is
  waived. No additional Windows account is required. T004, the protected-run
  part of T038, T029, and T041-T043 remain active and NOT VERIFIED; the waiver
  does not establish a trusted execution boundary or successful protected run.
- **D-05**: Resolved by the human-approved v1.4.0 amendment dated 2026-11-13.
  The application-level backup/recovery contract is in `spec.md`, `research.md`,
  and `plan.md`; Windows atomic visibility and crash durability are explicitly
  not guaranteed. This resolution does not resolve D-01.
- **Approval metadata**: T003 must reconcile the constitution/spec statuses
  against actual human records before implementation; do not invent dates.

### User Story Dependencies

- **User Story 4 (P1)**: First implementation increment because all task
  mutations rely on durable collection state.
- **User Story 1 (P1)**: Follows User Story 4; CRUD is the MVP API increment.
- **User Story 2 (P2)** and **User Story 3 (P2)**: Follow the shared task model,
  service, and API error contract; they can be developed in parallel only after
  the shared implementation and applicable D-01 review/enrollment requirements
  are satisfied.

### Parallel Opportunities

- T002 can proceed before approval; T001 must wait for T003. T001 is not
  parallel with the governance gate.
- T005 is resolved by the explicit human-approved amendment. T004 remains
  open pending active protected-workflow and execution-boundary verification.
- Story implementations and tests are present and pass local diagnostics.
  Their authoritative validation remains blocked until D-01 approval.
- The owner waiver removes only custom-bootstrap work in T037 and part of T038.
  Active protected-workflow verification remains in T004, T029, T038-T043.
  T044-T045 are later human actions after automated validation.
- User Stories 2 and 3 can proceed in parallel after shared files are stable;
  edits to `domain/service.py`, `api/routes.py`, and `api/schemas.py` must be
  coordinated to avoid conflicts.

### Parallel Examples by User Story

- **US4**: T008, T009, and T012 are complete under the approved contract.
  Local candidate tests pass; authoritative execution remains blocked by D-01.
- **US1**: After the gates clear, author T014 (`test_task_crud.py`), T015 (`test_id_allocation.py`), and T016 (`test_error_contract.py`) in parallel; implement service, schemas, routes, and error mapping in dependency order.
- **US2**: T021 is one test task; keep T022 and T023 sequential because service and route/schema changes share files.
- **US3**: T024 is one test task; implement T025 before T026 because the route depends on the transition service.

## Implementation Strategy

### MVP

The smallest useful end-to-end increment is User Story 4's JSON repository
followed by User Story 1's CRUD API. D-05 is resolved by v1.4.0. Local candidate
work and validation are diagnostic; authoritative validation and acceptance
remain blocked by D-01 and the human review/decision gates.

### Traceability

Test tasks explicitly cover every test-strategy mapping: AT-001 through AT-029
map respectively to AC-001 through AC-029. HT-001 and HT-002 are supplemental
and do not alter those mappings. No acceptance criterion is omitted; cross-cutting
harness/security criteria remain mandatory and cannot be removed or weakened to
unblock implementation.
