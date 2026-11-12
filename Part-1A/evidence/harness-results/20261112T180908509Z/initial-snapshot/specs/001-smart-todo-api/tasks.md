# Tasks: Smart Todo & Task Management API

**Input**: Design documents in `specs/001-smart-todo-api/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`,
`test-strategy.md`, and `contracts/openapi.yaml`.

**Planning basis**: This task list does not assert that the constitution or
feature specification is approved. The constitution records pending human
approval and spec v1.3.0 records pending human review; no approval records have
been verified in the project artifacts. T003 is a mandatory governance gate:
verify actual human records before relying on either artifact, and record only
dates present in those records. Do not infer or invent ratification or approval
dates. D-01 and D-05 remain explicit blocking gates.

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
independently; T001 is blocked on T003 approval.

- [ ] T001 BLOCKED (T003) Create or complete `pyproject.toml` only after T003 verifies actual human approval of the project and the exact package-version set: FastAPI 0.162.4, Pydantic 2.14.3, pytest 9.2.0, HTTPX 0.28.1, Ruff 0.17.4, Bandit 1.9.4, and Uvicorn 0.54.0. Generate `uv.lock`, verify the active interpreter and dependency resolution target Python 3.12, then run `uv lock --check --python 3.12` and `uv sync --locked`. Record the approved dependencies in `pyproject.toml`, `uv.lock`, and `specs/001-smart-todo-api/research.md`. Before T003, only read-only environment inspection (for example, `python --version` and `uv --version`) is permitted; do not create or modify either project file or install project dependencies.
- [x] T002 [P] Create the planned `src/`, `tests/`, `.harness/`, and `evidence/` directory structure from `plan.md`; preserve runtime-data and local-environment exclusions in `.gitignore`.

## Phase 2: Foundational Gates

**Purpose**: Resolve governance and trust prerequisites before any user-story
implementation or authoritative test execution.

- [ ] T003 BLOCKED (human governance): Verify actual human ratification/approval records for `.specify/memory/constitution.md` and `specs/001-smart-todo-api/spec.md`; verify approval of the exact dependency versions recorded in `specs/001-smart-todo-api/plan.md` and `research.md`; update statuses only when supported by actual records, record only dates explicitly present, and confirm which specification version/error-details schema is approved. Do not assume proposed v1.3.0 or the dependency list is approved, and do not invent dates.
- [ ] T004 [P] BLOCKED (D-01): Establish and verify the separate trusted Windows identity/ACL or protected CI environment; provision the canonical bootstrap runner from an administrator-controlled source independent of the repository; and establish the protected trust store, staging/evidence access controls, and out-of-band human administration channel. Confirm the coding-agent identity cannot administer the trusted boundary. This task establishes the protected environment only; T028-T036 create the untrusted runner and validation files, and T037-T038 review and enroll them. Do not treat repository location outside `src/` or the workspace as protection.
- [ ] T005 [P] BLOCKED (D-05): Resolve the Windows atomic-visibility requirement using supported-platform evidence documented in `specs/001-smart-todo-api/research.md` and `plan.md`. Do not claim `os.replace`, `ReplaceFileW`, or `MoveFileExW` meets the requirement without evidence. If no compliant approach is established, keep persistence implementation blocked pending an explicit human-approved specification amendment.
- [ ] T006 BLOCKED (T003): Verify `specs/001-smart-todo-api/contracts/openapi.yaml` against the human-approved `specs/001-smart-todo-api/spec.md`; confirm the approved error-details schema and every documented endpoint/status-code set, including existing error contracts. Correct the OpenAPI contract only to match the actually approved specification; if approval or the error-details amendment is unresolved, stop without treating a proposal as approved.
- [ ] T007 BLOCKED (T003-T006): Create the architecture scaffolding and application factory in `src/smart_todo/app.py`, `src/smart_todo/api/`, `src/smart_todo/domain/`, and `src/smart_todo/persistence/`; define the repository port separately from its JSON implementation and install application/API error translation; accept an explicit `Path`, otherwise use `SMART_TODO_STORE_PATH`, then `data/tasks.json`, without loading the store during app creation.

## Phase 3: User Story 4 - Keep Tasks Across Restarts (Priority: P1)

**Goal**: Persist and validate the JSON collection without losing valid data or
silently resetting malformed data.

**Independent Test**: Against an isolated store, restart and verify tasks and
`next_id`; inject malformed stored documents and persistence failures and verify
the specified error and preservation behavior.

### Tests for User Story 4

- [ ] T008 [US4] BLOCKED (D-01, D-05): Add AT-013, AT-014, and AT-015 tests in `tests/persistence/test_json_repository.py`; cover restart persistence, successful complete replacement, injected write/replacement failures with byte-identical prior data and unchanged memory, and request-time malformed-store errors with unchanged source bytes.
- [ ] T009 [US4] BLOCKED (D-01, D-05): Add AT-029 concurrency tests in `tests/concurrency/test_mutations.py`; verify serializable results, unique sequential IDs, no lost updates, persisted `next_id` and next ID after restart, failed-write rollback, and no assertion about request-to-ID ordering.

### Implementation for User Story 4

- [ ] T010 [US4] BLOCKED (D-01): Implement strict task and stored-document models in `src/smart_todo/domain/models.py`; enforce positive integer IDs (reject Booleans), trimmed 1-200 character titles, null or 0-2000 character descriptions, at most 20 distinct trimmed lowercase 1-32 character tags in lexicographic order, priorities `Low`/`Medium`/`High`, and statuses `Pending`/`In Progress`/`Completed`.
- [ ] T011 [US4] BLOCKED (D-01): Implement lazy JSON loading and complete validation in `src/smart_todo/persistence/json_repository.py`; require exactly root fields `next_id` and `tasks`, exactly the six task fields, unique IDs, `next_id` greater than every ID, duplicate-member detection, and request-time `MalformedStoredDataError` from `src/smart_todo/persistence/errors.py` without resetting or overwriting the store. Keep domain errors business-only; propagate repository exceptions without making the domain depend on JSON persistence.
- [ ] T012 [US4] BLOCKED (D-01, D-05): Implement complete candidate serialization to a same-directory temporary file and the verified Windows replacement mechanism in `src/smart_todo/persistence/json_repository.py`; on any reported write/replacement failure preserve the original bytes and do not publish candidate memory state.
- [ ] T013 [US4] BLOCKED (D-01, D-05): Serialize each instance's mutations and reads through the agreed synchronization boundary in `src/smart_todo/domain/service.py`; keep candidate state separate until persistence succeeds and ensure outcomes correspond to a serial execution.

## Phase 4: User Story 1 - Manage Tasks (Priority: P1)

**Goal**: Provide task creation, retrieval, listing, partial updates, and deletion
with deterministic identifiers and the documented API contract.

**Independent Test**: Complete create/read/update/list/delete against an
isolated store and verify IDs, representations, response codes, validation, and
error envelopes.

### Tests for User Story 1

- [ ] T014 [US1] BLOCKED (D-01, D-05): Add AT-001, AT-003, AT-004, AT-005, AT-016, and AT-019 API contract tests in `tests/api_contract/test_task_crud.py`; verify task lifecycle responses, `Location`, partial-update preservation, deletion, field boundaries, and all documented endpoint statuses.
- [ ] T015 [US1] BLOCKED (D-01, D-05): Add AT-002 ID-allocation tests in `tests/unit/test_id_allocation.py`; verify IDs start at 1, increment for successful creates, remain deterministic from identical state, and are not reused after deletion or restart.
- [ ] T016 [US1] BLOCKED (D-01): Add AT-018 and AT-020 error-contract tests in `tests/api_contract/test_error_contract.py`; cover malformed JSON, invalid IDs/query/body/fields/enums, exact error envelopes, exactly string fields `field`, `code`, `message`, empty `details` when no field information applies, deterministic ordering, and no internal details.

### Implementation for User Story 1

- [ ] T017 [US1] BLOCKED (D-01, D-05): Implement deterministic CRUD and ID allocation in `src/smart_todo/domain/service.py`; allocate from persisted `next_id` and increment only for a successfully persisted creation.
- [ ] T018 [US1] BLOCKED (D-01): Implement explicit create/update request and task response schemas in `src/smart_todo/api/schemas.py`; reject unknown fields and enforce the approved title/description bounds and null/partial-update semantics.
- [ ] T019 [US1] BLOCKED (D-01, D-05): Implement `POST /tasks`, `GET /tasks`, `GET /tasks/{id}`, `PATCH /tasks/{id}`, and `DELETE /tasks/{id}` in `src/smart_todo/api/routes.py`, preserving the OpenAPI contract and response codes.
- [ ] T020 [US1] BLOCKED (D-01): Implement common error translation in `src/smart_todo/api/errors.py` and application exception wiring in `src/smart_todo/app.py`; keep `src/smart_todo/domain/errors.py` limited to task/business errors, define repository errors in `src/smart_todo/persistence/errors.py`, and translate them at the application/API boundary while preserving `invalid_json`, `not_found`, `validation_error`, `malformed_stored_data`, and `persistence_error` envelopes and statuses.

## Phase 5: User Story 2 - Organize and Find Tasks (Priority: P2)

**Goal**: Normalize tags, filter by all requested tags, and sort priorities
deterministically.

**Independent Test**: Create tasks with overlapping tags and all priorities;
verify normalization, AND filtering, empty matches, priority order, and ID ties.

### Tests for User Story 2

- [ ] T021 [US2] BLOCKED (D-01, D-05): Add AT-006, AT-007, AT-008, AT-009, and AT-017 tests in `tests/api_contract/test_task_organization.py`; cover tag normalization/count/type/length, AND multi-tag filters, zero matches, priority values/default, priority sorting, and deterministic ties.

### Implementation for User Story 2

- [ ] T022 [US2] BLOCKED (D-01, D-05): Implement tag normalization, deduplication, AND filtering, priority sorting, and ID-ascending tie/default order in `src/smart_todo/domain/service.py`.
- [ ] T023 [US2] BLOCKED (D-01, D-05): Implement repeated `tag` and `sort=priority` query parsing and validation in `src/smart_todo/api/schemas.py` and `src/smart_todo/api/routes.py`; return `200`, `items: []`, and `count: 0` for no matches.

## Phase 6: User Story 3 - Track Task Progress (Priority: P2)

**Goal**: Support only permitted status transitions and preserve task state on
rejection.

**Independent Test**: Exercise every allowed, idempotent, and prohibited
transition and verify response codes and stored status.

### Tests for User Story 3

- [ ] T024 [US3] BLOCKED (D-01, D-05): Add AT-010, AT-011, and AT-012 tests in `tests/api_contract/test_status_transitions.py`; cover the `Pending` default, both permitted transitions, same-status no-op, every prohibited transition, and unchanged state on `409`.

### Implementation for User Story 3

- [ ] T025 [US3] BLOCKED (D-01, D-05): Implement lifecycle rules in `src/smart_todo/domain/service.py`; permit only `Pending -> In Progress` and `In Progress -> Completed`, make current-status requests no-ops, and reject every other transition without mutation.
- [ ] T026 [US3] BLOCKED (D-01, D-05): Implement `PATCH /tasks/{id}/status` and its request schema in `src/smart_todo/api/routes.py` and `src/smart_todo/api/schemas.py`; preserve `400`, `404`, `409`, `422`, and `500` contracts.

## Phase 7: Polish and Cross-Cutting Validation

**Purpose**: Complete cross-story determinism, harness protection, security,
quality gates, and attributable evidence.

- [ ] T027 BLOCKED (D-01, D-05): Add AT-021 sequential determinism tests in `tests/api_contract/test_determinism.py`; compare status, data, IDs, and ordering for identical request sequences and initial persisted state.
- [ ] T028 BLOCKED (D-01, T003, T004): Implement `Part-1A/.harness/run.ps1` and `.harness/instruction-files.json` as untrusted repository candidates. Do not execute the runner authoritatively until T038 enrolls it. The inventory lists only actual instruction/governing files affecting coding-agent behavior or validation, without wildcard paths; each entry contains `path`, `purpose`, `classification`, `sha256`, and `approval_reference` with exact values. Do not invent approval references. The canonical runner verifies the submitted runner, tests, controls, inventory, and each listed file against the separately protected baseline/approval records; only a verified immutable snapshot may execute. Stage all application source, tests, harness and dependency configuration, required project files, approved specifications, the inventory and listed files as the validation candidate. Exclude generated evidence, runtime data, virtual environments, caches, and enumerated ephemeral files from its digest. Capture commands/stdout/stderr/exit codes, bind results to the candidate digest, maintain the separate evidence-bundle manifest, fail closed with non-zero on unauthorized changes, and reject publication if the candidate or evidence bundle fails integrity checks. Repository location alone is not protection.
- [ ] T029 BLOCKED (D-01, T003, T028): Add AT-022 runner checks in `.harness/mandatory-checks.json` and `tests/harness_integrity/test_validation_pipeline.py`; require zero Ruff violations, all mandatory tests passing, full AC-to-test mapping, Bandit exit code/stdout/stderr/machine-readable findings and execution status, no external test network services, staged-snapshot imports, a pre-run validation candidate manifest, a separate integrity-verified evidence bundle manifest referencing the tested candidate digest, publication-candidate equality, and runner-generated results without human dispositions or ACCEPT/REJECT. Include supplemental HT-002 coverage for manifest separation and evidence integrity.
- [ ] T030 BLOCKED (D-01, T003, T028): Add AT-023 tamper-detection tests in `tests/harness_integrity/test_baseline_integrity.py`; use disposable trust-store/baseline fixtures to verify the first invocation uses the canonical runner and the repository runner is not executed before its hash is matched. Test unauthorized changes to the runner, tests, expected results, controls, `.harness/instruction-files.json`, and each inventoried file; verify rejection before application tests, no modified bytes execute, failure evidence is generated, and the runner exits non-zero. Test rejection of wildcard/unlisted inventory entries. Never modify or compromise the real canonical baseline.
- [ ] T031 BLOCKED (D-01, T003, T028): Add AT-024 approval-flow tests in `tests/harness_integrity/test_approval_records.py`; use disposable protected-store fixtures to reject unapproved, incomplete, tampered, or mismatched changes to tests, expected results, controls, the instruction inventory, and inventoried files, and accept only exact approved digests through the protected channel. Never edit real approval records or baselines.
- [ ] T032 BLOCKED (D-01, T003, T028): Add AT-025 architecture/runtime checks in `tests/harness_integrity/test_architecture.py`; verify Python 3.12, FastAPI/Pydantic use, route/service/persistence boundaries, service dependence on an abstract repository port, no domain import of the concrete JSON repository or persistence errors, and API-boundary translation of persistence exceptions.
- [ ] T033 BLOCKED (D-01, T003, T028): Add AT-026 repository-hygiene checks and synthetic fixtures in `tests/harness_integrity/test_repository_hygiene.py`; detect local environment files, credentials, and private keys and block publication on findings.
- [ ] T034 BLOCKED (D-01, T003, T028): Add AT-027 human security-review gate in `tests/harness_integrity/test_security_review_gate.py` and retain the review record under `evidence/security-review/`; require review of each Bandit finding, resolution or documented disposition and rationale, repository scope, reviewer identity/date, and a human determination that the gate is satisfied.
- [ ] T035 BLOCKED (D-01, T003, T028): Add AT-028 human decision-gate checks in `tests/harness_integrity/test_human_decision.py` and retain the decision under `evidence/human-decision/`; only a human-recorded `ACCEPT` may open publication, while `REJECT` or no decision blocks it.
- [ ] T036 BLOCKED (D-01, T003, T028): Add HT-001 in `tests/harness_integrity/test_staging_isolation.py`; use a disposable repository and trust-store fixture, stage its application and controls, then change the original working directory after staging. Verify the run still executes only staged bytes, imports the staged package, preserves the staged manifest, binds results to its hash, and rejects publication if the final candidate differs. Author the test before enrollment, but run it authoritatively only after T038. Never alter the real canonical baseline.
- [ ] T037 BLOCKED (D-01, T003, T008-T036): After all story work and harness candidate files are complete, have the human administrator independently review the exact initial repository runner, all mandatory tests (AT-001 through AT-029 and HT-001/HT-002), expected results, validation controls, `.harness/instruction-files.json`, and every file it lists; independently verify the inventory contains only actual approved files and no wildcards, calculate exact SHA-256 digests, and record the source commit outside the coding-agent-controlled process. Do not execute the repository runner authoritatively or enroll digests in this task.
- [ ] T038 BLOCKED (D-01, T037): Perform the initial trusted-runner bootstrap by enrolling the human-reviewed initial runner, tests, controls, `.harness/instruction-files.json`, listed instruction files, and exact baseline digests in the protected trust store through the out-of-band human-controlled process. Record the initial approver, actual approval date, rationale, source commit, and approved file digests in the protected approval register. Configure the first authoritative execution to invoke the canonical runner from the protected trust store; it must verify repository candidates against the canonical baseline before execution. Require a separate recorded human approval and protected baseline update for subsequent changes; never invent approval metadata.
- [ ] T039 BLOCKED (D-01, T028, T038): Establish the evidence layout under `evidence/` and the protected store. Before each authoritative run, calculate a sorted validation candidate manifest over all application, test, harness configuration (including `.harness/instruction-files.json`), dependency, specification, required project, and exact inventoried instruction files used by validation; exclude generated evidence, runtime data, virtual environments, caches, and enumerated ephemeral files. Separately calculate an evidence bundle manifest covering runner results/logs, initial/final snapshot references, failures, repairs, and later human review/decision records; bind it to the exact candidate digest and verify its integrity before publication. Evidence generation must not change the candidate digest; prevent manual edits to runner-generated results.
- [ ] T040 BLOCKED (D-01, D-05, T001-T039): Supporting documentation and deployment verification only (not a functional requirement or acceptance criterion): validate `specs/001-smart-todo-api/quickstart.md` against the approved Windows PowerShell/uv setup and the completed implementation before the initial validation candidate is frozen. Record documentation verification in evidence without changing application scope.
- [ ] T041 BLOCKED (D-01, D-05, T001-T040): Perform the first authoritative run from the canonical runner in the protected trust store after successful T038 bootstrap and baseline enrollment. Before any repair, preserve the first generated application snapshot. Calculate and retain the validation candidate manifest, run all mandatory checks against the immutable staged candidate, and capture genuine initial results, commands, tool versions, stdout/stderr, and failed checks. Generate an initial evaluation record and evidence bundle manifest bound to the candidate digest, then provide the actual structured failure evidence to the coding agent. Do not execute an unverified repository runner and never manufacture failures.
- [ ] T042 BLOCKED (D-01, D-05, T041): Consume T041's genuine initial run evidence. For each actual failure, record the failed check, mapped requirement, expected behaviour, observed behaviour, and stdout/stderr. Repair application behavior only when evidence shows the application is at fault, without weakening approved requirements, tests, or harness, and preserve each repair and its evidence. If the harness, tests, controls, or cause is in question, stop for the required human review/approval rather than changing them. If there are no application failures, record that no repair was required. Re-run the exact same mandatory controls against the resulting staged candidate, calculating a new validation candidate manifest if any candidate file changed; preserve every run's results and candidate-digest reference in the evidence bundle and regenerate its integrity manifest.
- [ ] T043 BLOCKED (D-01, D-05, T038, T042): Run final trusted automated validation through the canonical runner; require all mandatory tests to pass, Ruff to report zero violations, and Bandit to execute while preserving exit code, stdout, stderr, machine-readable findings, and execution status. Verify repository hygiene, candidate-manifest equality, evidence-bundle integrity, and that automated results contain no human disposition or ACCEPT/REJECT. Record final results and candidate digest.
- [ ] T044 BLOCKED (D-01, T043): HUMAN ACTION — after T043 final automated validation, conduct and record the final repository security review. Review each Bandit finding and repository-hygiene results; record resolution or documented disposition and rationale for findings, reviewer identity, actual review date, reviewed scope, and the human determination whether the security-review gate is satisfied. Bind the record to the validated candidate digest and refresh the evidence manifest. Publication remains blocked if the review is missing or incomplete.
- [ ] T045 BLOCKED (D-01, T043, T044): HUMAN ACTION — after final automated validation and T044 security review, record exactly one explicit `ACCEPT` or `REJECT`, with human reviewer identity/date, the validated candidate digest, and the current evidence bundle manifest digest (covering final automated results and the security review, but not the decision record itself). After recording the decision, regenerate the final evidence bundle manifest to cover the decision and verify bundle integrity. Automated tools must never generate, infer, or alter this decision. Only a human-recorded `ACCEPT`, with the publication candidate matching the tested candidate and the final evidence bundle intact, permits publication; `REJECT` or no valid decision blocks publication.

## Dependencies and Execution Order

### Phase Dependencies

- **Phase 1**: T002 may proceed independently. T001 is blocked by T003 and
  must not create/modify `pyproject.toml` or `uv.lock`, or install dependencies,
  before human approval is verified.
- **Phase 2**: T003 is a human governance gate. T004 (D-01) and T005 (D-05)
  are independent but both block feature implementation and authoritative
  validation. T001 depends on T003; T006 depends on T003; T007 depends on
  T003-T006.
- **User Story 4 (P1)**: Depends on T003-T007; persistence writes and mutation
  tests additionally require D-05 resolution.
- **User Story 1 (P1)**: Depends on the persistence layer in User Story 4 and
  the trusted test boundary in T004.
- **User Stories 2 and 3 (P2)**: Depend on the core task/service/API layers and
  the same D-01/D-05 gates.
- **Polish**: Depends on all story work and the trusted runner. Complete T040
  quickstart documentation/deployment verification before freezing the
  candidate; then execute T041 initial validation, T042 repair/revalidation if
  needed, T043 final automated validation, T044 actual human security review,
  and T045 actual human ACCEPT/REJECT decision in that order.

### Blocking Decision Dependencies

- **D-01**: T004 is blocked pending an actual protected identity/ACL or CI setup
  and successful verification. T028-T036 then create the untrusted runner and
  mandatory validation files; T037 independently reviews the exact files and
  T038 enrolls their approved digests through the protected process.
  Authoritative execution is blocked until enrollment. All mandatory test,
  harness, evidence, and validation tasks (T028-T045) remain BLOCKED until the
  corresponding D-01 steps are verified.
- **D-05**: T005 is blocked pending a Windows replacement approach proven to
  preserve the specified data-integrity guarantee. Atomic-write, mutation,
  persistence-dependent story, initial/final validation, human review, and
  publication-decision tasks remain BLOCKED until then. No fallback that
  weakens the requirement is permitted.
- **Approval metadata**: T003 must reconcile the constitution/spec statuses
  against actual human records before implementation; do not invent dates.

### User Story Dependencies

- **User Story 4 (P1)**: First implementation increment because all task
  mutations rely on durable collection state.
- **User Story 1 (P1)**: Follows User Story 4; CRUD is the MVP API increment.
- **User Story 2 (P2)** and **User Story 3 (P2)**: Follow the shared task model,
  service, and API error contract; they can be developed in parallel only after
  the shared implementation and D-01/D-05 gates are complete.

### Parallel Opportunities

- T002 can proceed before approval; T001 must wait for T003. T001 is not
  parallel with the governance gate.
- T004 and T005 are independent prerequisite investigations, though both remain
  blocked until their respective external/human conditions are satisfied.
- After D-01 is resolved, independent test files within each story can be
  authored in parallel, subject to human approval and protected baseline update.
- The D-01 sequence is T004 -> T028 -> T029-T036 -> T037 -> T038. AT-022
  through AT-028 and HT-001/HT-002 are authored before human review, then run
  only after T038 enrollment. T039-T043 require the enrolled canonical runner
  and verified staging path; T044-T045 are actual human actions after automated
  validation.
- User Stories 2 and 3 can proceed in parallel after shared files are stable;
  edits to `domain/service.py`, `api/routes.py`, and `api/schemas.py` must be
  coordinated to avoid conflicts.

### Parallel Examples by User Story

- **US4**: After D-01 and D-05 clear, author T008 (`tests/persistence/test_json_repository.py`) and T009 (`tests/concurrency/test_mutations.py`) in parallel; the files are separate. Implement repository reads/writes before the mutation coordinator.
- **US1**: After the gates clear, author T014 (`test_task_crud.py`), T015 (`test_id_allocation.py`), and T016 (`test_error_contract.py`) in parallel; implement service, schemas, routes, and error mapping in dependency order.
- **US2**: T021 is one test task; keep T022 and T023 sequential because service and route/schema changes share files.
- **US3**: T024 is one test task; implement T025 before T026 because the route depends on the transition service.

## Implementation Strategy

### MVP

The smallest useful end-to-end increment is User Story 4's compliant JSON
repository followed by User Story 1's CRUD API. Neither may start until D-01
and D-05 and the governance status gate are resolved. Validate each increment
with its approved AT tests through the trusted runner.

### Traceability

Test tasks explicitly cover every test-strategy mapping: AT-001 through AT-029
map respectively to AC-001 through AC-029. HT-001 and HT-002 are supplemental
and do not alter those mappings. No acceptance criterion is omitted; cross-cutting
harness/security criteria remain mandatory and cannot be removed or weakened to
unblock implementation.
