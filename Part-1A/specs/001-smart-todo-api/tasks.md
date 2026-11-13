# Tasks: Smart Todo & Task Management API

**Input**: Design documents in `specs/001-smart-todo-api/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`,
`test-strategy.md`, and `contracts/openapi.yaml`.

**Planning basis**: Human approval was recorded on 2026-11-12 for constitution
v1.1.0, feature specification v1.3.0, and the implementation plan. The approved
plan/research record contains the exact dependency versions, and approved
specification v1.3.0 establishes the error-details schema; T003 is complete.
The human-approved v1.4.0 amendment on 2026-11-13 resolves D-05 by replacing
the unsupported Windows atomic-visibility/crash-durability guarantee with the
application-level recovery contract. D-01 remains an explicit trust-boundary
and authoritative-validation gate.

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

- [x] T003 Verify the human approval recorded on 2026-11-12 for constitution v1.1.0, feature specification v1.3.0, and the implementation plan. Confirm the plan/research dependency set (FastAPI 0.162.4, Pydantic 2.14.3, pytest 9.2.0, HTTPX 0.28.1, Ruff 0.17.4, Bandit 1.9.4, and Uvicorn 0.54.0) and the approved v1.3.0 error-details schema. This records the user's explicit approval in this interaction; it is not a protected approval-register reference. D-01 remained blocked; D-05 was later resolved by the separately approved v1.4.0 amendment dated 2026-11-13.
- [ ] T004 [P] BLOCKED (D-01 implementation): Verify the configured GitHub `main` ruleset and which actors can administer the workflow, baseline, approval register, staging, and evidence. Do not create Windows accounts. Verify the trusted workflow runs from protected `main`, uses a read-only token, provides no secrets to candidate code, and cannot be bypassed by selecting a candidate-controlled workflow definition. A protected-branch flag alone is insufficient; complete verification requires a human-approved baseline and a successful protected workflow run.
- [x] T005 [P] Resolve D-05 by applying the explicitly human-approved 2026-11-13 amendment to feature specification v1.4.0. Retain JSON persistence; replace the unsupported Windows atomic-visibility/crash-durability guarantee with the application-level backup, byte-verification, restoration, and fail-closed contract. Update `research.md`, `plan.md`, AC-014/test strategy, and related harness checks. Do not claim that `os.replace`, `ReplaceFileW`, `MoveFileExW`, or local tests establish Windows atomic visibility or crash durability. D-01 remains independently blocked.
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
- [x] T028 Implement the local harness as an untrusted repository candidate and add the protected-main GitHub Actions workflow plus bootstrap files. The workflow checks out trusted `main` separately from an explicit candidate SHA, uses read-only permission without candidate secrets, verifies approved digests, stages run-specific bytes, checks integrity before and after execution, and retains artifacts. The baseline and consolidated approval register remain pending; D-01 is not complete.
- [ ] T029 BLOCKED (D-01): Complete and verify AT-022 coverage for zero Ruff findings, all tests, full AC mapping, Bandit output, network isolation, staging integrity, evidence-manifest integrity, publication equality, and non-human automated results. Candidate workflow and evidence scripts exist, but no protected run or complete traceability/hygiene gate has been verified.
- [x] T030 Add AT-023 disposable-baseline tamper tests in `tests/harness_integrity/test_github_trust_bootstrap.py`; verify approved control, inventory, instruction, dependency, and test digests; reject unapproved changes before staging; and verify run-specific staged bytes against their manifest. These are local candidate tests, not canonical-runner enrollment.
- [x] T031 Add AT-024 consolidated-register tests in `tests/harness_integrity/test_github_trust_bootstrap.py`; verify the ten-file inventory, exact current digests, pending approval fields, and a synthetic approved disposable baseline. No real approval data or baseline enrollment is created.
- [x] T032 Add AT-025 architecture/runtime checks in `tests/harness_integrity/test_architecture.py`; verify Python 3.12, FastAPI/Pydantic use, route/service/persistence boundaries, service dependence on an abstract repository port, no domain import of the concrete JSON repository or persistence errors, and API-boundary translation of persistence exceptions. Local candidate tests pass; authoritative validation remains blocked by D-01.
- [x] T033 Add AT-026 repository-hygiene checks and synthetic fixtures in `tests/harness_integrity/test_repository_hygiene.py`; detect local environment files, credentials, and private keys and block publication on findings while excluding only preserved synthetic scanner fixture artifacts from historical evidence. Local scan verifies the publication candidate has zero findings; authoritative publication remains blocked by D-01.
- [ ] T034 BLOCKED (D-01, T003, T028): Add AT-027 human security-review gate in `tests/harness_integrity/test_security_review_gate.py` and retain the review record under `evidence/security-review/`; require review of each Bandit finding, resolution or documented disposition and rationale, repository scope, reviewer identity/date, and a human determination that the gate is satisfied.
- [ ] T035 BLOCKED (D-01, T003, T028): Add AT-028 human decision-gate checks in `tests/harness_integrity/test_human_decision.py` and retain the decision under `evidence/human-decision/`; only a human-recorded `ACCEPT` may open publication, while `REJECT` or no decision blocks it.
- [x] T036 Add HT-001 staging-isolation coverage in `tests/harness_integrity/test_github_trust_bootstrap.py`; stage a disposable candidate, mutate its source afterward, verify the staged snapshot remains unchanged, and detect staged-byte tampering. It is not authoritative until D-01 enrollment and protected execution.
- [ ] T037 HUMAN ACTION (D-01): Independently review the exact initial workflow and trust scripts, all mandatory tests (AT-001 through AT-029 and HT-001/HT-002), expected results, validation controls, `.harness/instruction-files.json`, and its ten listed files. Verify the inventory has no wildcards, review the exact digests in the consolidated register, and record the actual source commit and approval details in that one register. Do not run the workflow or enroll a baseline before approval.
- [ ] T038 HUMAN ACTION (D-01, T037): Merge the reviewed workflow and exact digest baseline through protected `main`; record the actual approver, date, rationale, source commit, and approval reference in `.harness/trust/approval-register.json`. Then dispatch from `main` with an explicit candidate SHA and verify that the trusted workflow fails closed on tampering and completes a protected run. Never invent approval metadata.
- [ ] T039 BLOCKED (D-01, T028, T038): After bootstrap, verify the workflow artifact evidence layout and protected retention. Each run must bind the sorted candidate manifest to the candidate SHA, exclude evidence/runtime/cache data from candidate digesting, retain complete command logs and results, and provide a separately sealed evidence manifest. Verify the workflow artifact and publication-candidate equality before publication; evidence generation must not alter the candidate digest.
- [x] T040 Supporting documentation and deployment verification only (not a functional requirement or acceptance criterion): update `specs/001-smart-todo-api/quickstart.md` to the implemented API, actual Windows PowerShell/uv commands, local diagnostic limitation, and protected-main workflow path. Local commands and protected workflow remain distinct.
- [ ] T041 BLOCKED (D-01, T001-T040): Perform the first authoritative run from the canonical runner in the protected trust store after successful T038 bootstrap and baseline enrollment. Before any repair, preserve the first generated application snapshot. Calculate and retain the validation candidate manifest, run all mandatory checks against the immutable staged candidate, and capture genuine initial results, commands, tool versions, stdout/stderr, and failed checks. Generate an initial evaluation record and evidence bundle manifest bound to the candidate digest, then provide the actual structured failure evidence to the coding agent. Do not execute an unverified repository runner and never manufacture failures.
- [ ] T042 BLOCKED (D-01, T041): Consume T041's genuine initial run evidence. For each actual failure, record the failed check, mapped requirement, expected behaviour, observed behaviour, and stdout/stderr. Repair application behavior only when evidence shows the application is at fault, without weakening approved requirements, tests, or harness, and preserve each repair and its evidence. If the harness, tests, controls, or cause is in question, stop for the required human review/approval rather than changing them. If there are no application failures, record that no repair was required. Re-run the exact same mandatory controls against the resulting staged candidate, calculating a new validation candidate manifest if any candidate file changed; preserve every run's results and candidate-digest reference in the evidence bundle and regenerate its integrity manifest.
- [ ] T043 BLOCKED (D-01, T038, T042): Run final trusted automated validation through the canonical runner; require all mandatory tests to pass, Ruff to report zero violations, and Bandit to execute while preserving exit code, stdout, stderr, machine-readable findings, and execution status. Verify repository hygiene, candidate-manifest equality, evidence-bundle integrity, and that automated results contain no human disposition or ACCEPT/REJECT. Record final results and candidate digest.
- [ ] T044 BLOCKED (D-01, T043): HUMAN ACTION — after T043 final automated validation, conduct and record the final repository security review. Review each Bandit finding and repository-hygiene results; record resolution or documented disposition and rationale for findings, reviewer identity, actual review date, reviewed scope, and the human determination whether the security-review gate is satisfied. Bind the record to the validated candidate digest and refresh the evidence manifest. Publication remains blocked if the review is missing or incomplete.
- [ ] T045 BLOCKED (D-01, T043, T044): HUMAN ACTION — after final automated validation and T044 security review, record exactly one explicit `ACCEPT` or `REJECT`, with human reviewer identity/date, the validated candidate digest, and the current evidence bundle manifest digest (covering final automated results and the security review, but not the decision record itself). After recording the decision, regenerate the final evidence bundle manifest to cover the decision and verify bundle integrity. Automated tools must never generate, infer, or alter this decision. Only a human-recorded `ACCEPT`, with the publication candidate matching the tested candidate and the final evidence bundle intact, permits publication; `REJECT` or no valid decision blocks publication.

## Dependencies and Execution Order

### Phase Dependencies

- **Phase 1**: T002 may proceed independently. T001 is blocked by T003 and
  must not create/modify `pyproject.toml` or `uv.lock`, or install dependencies,
  before human approval is verified.
- **Phase 2**: T003 is a human governance gate. T005 is complete through the
  approved v1.4.0 amendment. T004 (D-01) still blocks approved enrollment and
  authoritative validation. T001 depends on T003; T006 depends on T003; T007
  depends on T003-T006.
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

- **D-01**: The design direction is closed on GitHub protected `main`; the
  human reports that the branch ruleset is configured. No additional Windows
  account is required. T028-T036 implement candidate controls and tests locally.
  T004 and T037-T038 remain verification/approval steps. Authoritative execution
  is blocked until the workflow and digest baseline are approved on `main`, the
  execution boundary is verified, and an actual protected run succeeds.
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
  open pending protected-workflow and approval-boundary verification.
- Story implementations and tests are present and pass local diagnostics.
  Their authoritative validation remains blocked until D-01 approval.
- The D-01 sequence is T028-T036 -> T037 -> T038 -> T041-T043. T037-T038 are
  human review/bootstrap actions; T039-T043 require a successful protected
  workflow run. T044-T045 are later human actions after automated validation.
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
