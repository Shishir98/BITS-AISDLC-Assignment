# Tasks: Natural-Language Reminder Agent

**Input**: Design documents from
`/specs/001-natural-language-reminder-agent/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`,
`contracts/`, and `evaluation-strategy.md`

**Tests**: Contract/domain tests may use an Ollama HTTP test double. Final
evaluation evidence MUST use three independent actual Ollama model generations per
case; test doubles and fixtures must never create evaluation evidence or a feature
PASS.

**Organization**: Tasks are ordered by shared setup/foundation and then by
independently testable user story, followed by actual-model evaluation and final
verification.

## Phase 1: Setup

**Purpose**: Establish the Python 3.12/uv project without adding application
features.

- [ ] T001 Create the pinned Python 3.12, FastAPI, Pydantic, HTTPX, JSON Schema, PyYAML, pytest, Ruff, and uv project configuration in `pyproject.toml`.
- [ ] T002 [P] Document the local Ollama architecture and proposal-only product boundary in `README.md`.
- [ ] T003 Generate and verify the dependency lockfile `uv.lock` using the selected versions from `pyproject.toml`.

## Phase 2: Foundational Contracts and Local Runtime

**Purpose**: Define shared validation, temporal, Ollama, prompt, and API boundaries
before implementing any intent.

- [ ] T004 [P] Write response/request contract tests in `tests/api_contract/test_interpretation_contract.py` for required fields, forbidden extra fields, enums, and ready/clarification/unsupported relationships.
- [ ] T005 [P] Write deterministic timezone and explicit-reference tests in `tests/unit/test_temporal.py` for offsets, future boundaries, rollover, and ambiguous/nonexistent local times.
- [ ] T006 Implement strict request/result Pydantic models in `src/reminder_agent/schemas.py` from `specs/001-natural-language-reminder-agent/contracts/interpretation.openapi.yaml`.
- [ ] T007 Implement IANA timezone and temporal validation helpers in `src/reminder_agent/temporal.py` using `zoneinfo`.
- [ ] T008 [P] Write Ollama configuration and endpoint-mode tests in `tests/unit/test_configuration.py` for defaults, required model, validation, and non-loopback warning behavior.
- [ ] T009 Implement `OLLAMA_BASE_URL`, `OLLAMA_MODEL` (default `qwen3.5:9b`), `OLLAMA_TIMEOUT`, `MODEL_TEMPERATURE` (`0.2`), `MODEL_TOP_P` (`0.9`), and `MODEL_CONTEXT_LENGTH` (`4096`) handling in `src/reminder_agent/config.py`; use no API key or cloud credential.
- [ ] T010 [P] Write local model discovery, error mapping, and HTTP payload tests in `tests/unit/test_ollama_client.py` using an HTTP test double only.
- [ ] T011 Implement the Ollama local HTTP client and `/api/tags` model preflight in `src/reminder_agent/ollama_client.py`; reject missing/remote models and map runtime failures to the specified error codes.
- [ ] T012 [P] Write schema-in-prompt and structured-output request tests in `tests/unit/test_prompt_contract.py`.
- [ ] T013 Create the versioned system prompt at `prompts/system_prompt.md` and implement its loader/schema-digest metadata in `src/reminder_agent/prompts.py`; pass the approved schema in Ollama `format` where supported and include contract requirements in the system prompt.
- [ ] T014 Implement the shared interpretation orchestration in `src/reminder_agent/service.py`; independently validate every model result and fail closed.
- [ ] T015 Implement `POST /v1/reminders/interpret` and the distinct error response mapping in `src/reminder_agent/api.py`.

**Checkpoint**: Contracts, local runtime, prompts, and API boundary are testable
with HTTP test doubles; no fixture can be emitted as final evaluation evidence.

## Phase 3: User Story 1 - Propose a New Reminder (Priority: P1, MVP)

**Goal**: Return a ready CREATE proposal only when description and exact future
time are clear.

**Independent Test**: Exercise complete and paraphrased CREATE requests against
fixed temporal context; incomplete requests must clarify and never be ready.

- [ ] T016 [P] [US1] Write CREATE behavior and missing-field tests in `tests/unit/test_create_interpretation.py` for title extraction, future time, paraphrases, missing description, missing exact time, and non-invention.
- [ ] T017 [US1] Implement CREATE interpretation and response relationships in `src/reminder_agent/service.py` to satisfy AC-001, AC-002, and AC-003.

**Checkpoint**: CREATE requests pass independently with no reminder persistence
or execution.

## Phase 4: User Story 2 - Propose a Reminder Change (Priority: P2)

**Goal**: Distinguish RESCHEDULE from SNOOZE and require the target and relevant
new time or positive duration.

**Independent Test**: Exercise complete and incomplete RESCHEDULE/SNOOZE requests
against fixed temporal context; each intent must satisfy its own contract.

- [ ] T018 [P] [US2] Write RESCHEDULE and SNOOZE behavior tests in `tests/unit/test_change_interpretation.py` for target extraction, new time, positive whole-minute duration, missing fields, and intent distinction.
- [ ] T019 [US2] Implement RESCHEDULE and SNOOZE interpretation and response relationships in `src/reminder_agent/service.py` to satisfy AC-004, AC-005, and AC-006.

**Checkpoint**: Both change intents pass independently and remain proposal-only.

## Phase 5: User Story 3 - Resolve Ambiguity and Reject Unsupported Requests (Priority: P1)

**Goal**: Provide non-actionable clarification or unsupported outcomes and preserve
the local-only and fail-closed boundaries.

**Independent Test**: Exercise missing/ambiguous, malformed-language, unsupported,
prompt-injection, chain-of-thought, and action/tool requests; every critical
invariant must pass.

- [ ] T020 [P] [US3] Write clarification, unsupported, privacy, and adversarial behavior tests in `tests/unit/test_safety.py` for AC-006 through AC-016, AC-019 through AC-021, and AC-023.
- [ ] T021 [US3] Implement clarification and unsupported result handling in `src/reminder_agent/service.py`; never make incomplete or unsupported requests ready.
- [ ] T022 [US3] Implement non-persistent request handling and safe error responses in `src/reminder_agent/api.py`; distinguish Ollama failures, invalid model output, and application errors without fabricated success; preserve the first complete source/prompt/context snapshot before harness implementation.

**Checkpoint**: Unsafe, incomplete, unsupported, remote-model, and runtime-failure
cases cannot produce an actionable response.

## Phase 6: Actual-Model Evaluation and Evidence

**Purpose**: Implement the pre-established scoring gates, provenance manifest, and
three actual local-model runs per case.

- [ ] T023 [P] Create the 19-case baseline dataset in `evals/dataset.json` with 5 representative, 4 boundary, 4 ambiguous/missing, 2 malformed-language, and 4 adversarial/guardrail cases; include separate boundary cases for past/future, calendar rollover, nonexistent DST, and repeated DST times, and map every case to FR and AC IDs.
- [ ] T024 [P] Write scoring-formula and infrastructure-classification tests in `tests/evaluation/test_evaluation.py` for AC-017, AC-018, AC-022, and AC-024; fixtures may test scoring code but must not be written as evaluation evidence or yield PASS.
- [ ] T025 Implement evaluator preflight and three independent actual Ollama generations per case in the single integrated `.harness/run_evaluation.py`; verify `OLLAMA_NO_CLOUD=1` in the restarted Ollama server process and the actual local model inventory; never infer local-only mode from the FastAPI localhost URL or use mocked outputs/cloud fallback.
- [ ] T026 Record server-process configuration evidence, actual local model inventory, Ollama version, model ID/digest/details, prompt version/digest, effective parameters including actual temperature/top-p/context length, `ollama ps` offload observation, dataset digest, fixed temporal inputs, all three raw generations, and exact-output variation in `evidence/evaluations/<run-id>/`.
- [ ] T027 Implement all three validation layers, scoring, and status classification in `.harness/run_evaluation.py`; any runtime/infrastructure call failure makes the run incomplete with no successful 57-generation claim, while `INVALID_MODEL_OUTPUT` is a completed structural/semantic failure.
- [ ] T028 Validate `evals/dataset.json` distribution and per-case traceability; require all 57 actual generations for a complete baseline run and enforce approved thresholds and equal case-run property weighting without modifying thresholds.

## Phase 7: Final Verification and Documentation

**Purpose**: Verify the full implementation against the real local model and
document the local setup.

- [ ] T029 [P] Update `README.md` with Ollama installation, cloud-disable, environment configuration, and validation instructions from `specs/001-natural-language-reminder-agent/quickstart.md`.
- [ ] T030 Add API-level integration tests in `tests/integration/test_interpretation_api.py` for valid responses, invalid requests, and all distinct runtime errors.
- [ ] T031 Run contract, unit, integration, Ruff, and actual local-model evaluation checks; record evidence in `evidence/evaluations/`, preserve final source-state evidence, and confirm all 57 baseline generations and gates before reporting PASS.
- [ ] T032 Update `specs/001-natural-language-reminder-agent/traceability.md` with final test/evidence references and verify every FR and AC has executable coverage.

## Dependencies and Execution Order

### Phase Dependencies

- **Phase 1** has no dependencies.
- **Phase 2** depends on Phase 1 and blocks all user-story implementation.
- **Phase 3** depends on the shared contract, local runtime, and prompt boundary in
  Phase 2.
- **Phase 4** depends on Phase 2 and follows Phase 3 because both intent paths
  extend the shared interpretation orchestrator.
- **Phase 5** follows intent handling so safety tests cover all supported result
  types.
- **Phase 6** depends on completed story behavior and a locally installed Ollama
  model.
- **Phase 7** depends on the evaluation harness and all supported intent behavior.

### User Story Dependencies

- **US1 (P1)**: Begins after Phase 2; delivers the MVP CREATE proposal.
- **US2 (P2)**: Begins after US1 because both extend the shared dispatcher, but
  its behavior has independent tests.
- **US3 (P1)**: Begins after US1 and US2 so guardrail tests cover all supported
  result types; clarification and unsupported outcomes remain independently
  testable.

### Parallel Opportunities

- T002 can run alongside T001; T004, T005, T008, T010, and T012 are separate test
  files and can be authored in parallel after setup.
- T016, T018, and T020 are independent story test files; each story's
  implementation follows its tests.
- T023 and T024 can be authored in parallel; the runner T025 depends on their
  schemas and scoring behavior.
- User stories are intentionally not marked parallel because they modify the
  shared interpretation orchestrator.

## Implementation Strategy

### MVP First

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 and validate the CREATE vertical slice independently with
   local Ollama.
3. Stop for MVP validation before adding RESCHEDULE, SNOOZE, and broader
   guardrails.

### Incremental Delivery

1. Add RESCHEDULE and SNOOZE after the shared foundation.
2. Add clarification, unsupported, privacy, and adversarial safety behavior.
3. Add the traceable dataset and actual-model evaluation evidence.
4. Run all thresholds unchanged and report PASS only if every gate is satisfied.

## Notes

- `[P]` indicates distinct files with no dependency on an unfinished task.
- Tests precede implementation within each user story.
- HTTP test doubles are limited to tests; final evaluation evidence must contain
  actual local Ollama outputs.
- No task creates reminder persistence, delivery, scheduler, queue, calendar,
  authentication, approval, signing, or protected-runner infrastructure.
