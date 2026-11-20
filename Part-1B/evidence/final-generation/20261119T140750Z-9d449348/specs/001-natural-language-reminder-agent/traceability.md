# Requirements and Evaluation Traceability

The 19-case baseline dataset is maintained at `evals/dataset.json` and evaluated
by the single runner `.harness/run_evaluation.py`. Every case includes FR/AC
identifiers, deterministic expectations, property checks, and critical-invariant
checks. Actual generation evidence is stored under
`evidence/evaluations/<run-id>/`; infrastructure-blocked runs are incomplete and
do not produce scores or PASS.

| Requirement | Acceptance criteria | Planned verification/tasks | Minimum dataset/evidence coverage |
|---|---|---|---|
| FR-001 | AC-008, AC-009, AC-010 | T004, T006, T015, T030 | All valid evaluation cases |
| FR-002 | AC-001 | T016-T019, T023, T025 | Representative CREATE, RESCHEDULE, SNOOZE variants |
| FR-003 | AC-002, AC-003 | T016-T017 | Complete, paraphrased, missing title, missing exact time |
| FR-004 | AC-004, AC-006 | T018-T019 | Complete target/time, missing target/time |
| FR-005 | AC-005, AC-006 | T018-T019 | Complete target/duration, missing target/duration, invalid duration |
| FR-006 | AC-003, AC-006 | T020-T021, T023, T025 | Every missing/ambiguous mandatory-field case |
| FR-007 | AC-007 | T020-T021, T023, T025 | Unsupported operation and adversarial unsupported intent |
| FR-008 | AC-008, AC-009 | T004, T006, T030 | All successful result classes |
| FR-009 | AC-009, AC-010, AC-011 | T005, T007, T023, T025 | Separate baseline cases: past/future reference boundary, calendar rollover, nonexistent DST local time, ambiguous repeated DST local time |
| FR-010 | AC-012 | T010-T011, T014, T020, T022 | Malformed/inconsistent actual model output |
| FR-011 | AC-013, AC-014, AC-020 | T012-T014, T020-T021 | Injection, chain-of-thought, tool/action attempts |
| FR-012 | AC-015 | T008-T009, T011 | Local configuration, no API key or cloud credential |
| FR-013 | AC-014, AC-016, AC-023 | T020-T022, T030 | No action, persistence, telemetry, or cloud transmission |
| FR-014 | AC-017, AC-018, AC-022, AC-024 | T023-T028, T031-T032 | 19-case baseline, every case maps to FR/AC IDs, 57 individual actual generations |
| FR-015 | AC-019, AC-021 | T008-T011, T025, T030 | Installed model, runtime reachability, endpoint mode, distinct errors |
| FR-016 | AC-020 | T012-T014, T030 | Schema passed to structured generation and prompt; independent validation |
| FR-017 | AC-017, AC-022, AC-024 | T023-T028, T031-T032 | Ollama/server config and model inventory provenance, prompt/dataset metadata, all 57 actual outputs and genuine variation records |
| FR-018 | AC-023 | T020-T022, T030-T032 | No external inference, telemetry, remote logging, or app persistence |

## Acceptance-Criteria Coverage

Every AC is linked to its governing FR above. The dataset must cover all
representative, boundary, ambiguous/missing, malformed-language, and
adversarial/guardrail categories. Each case is evaluated through three independent
actual local-model calls with unchanged inputs and generation settings. Critical
safety criteria are mandatory gates and cannot be offset by semantic scores.

## Evidence and Result Semantics

- Ollama unavailability, missing model, or timeout makes the run incomplete with
  infrastructure-blocked reason; it produces no semantic score or PASS.
- Application errors are reported separately from semantic failures.
- Invalid actual model output counts as a structural/semantic failure.
- Unit-test fixtures and HTTP test doubles may test the scorer/client but never
  populate final evaluation evidence.
- The evaluation harness alone may persist actual generated outputs and
  reproducibility metadata in `evidence/evaluations/<run-id>/`.

## Executable Verification Index

| Concern / criteria | Executable verification |
|---|---|
| Strict request/result schema, response relationships, OpenAPI publication (AC-008, AC-009, AC-015) | `tests/api_contract/test_interpretation_contract.py`, `tests/integration/test_interpretation_api.py` |
| Intent behavior, required-field clarification, paraphrases, and safety (AC-001-007, AC-013-014) | `tests/unit/test_create_interpretation.py`, `tests/unit/test_change_interpretation.py`, `tests/unit/test_safety.py` |
| Explicit reference time, timezone offsets, rollover, past and DST boundaries (AC-009-011) | `tests/unit/test_temporal.py`, all applicable `evals/dataset.json` cases |
| Ollama configuration, installed-model discovery, structured output, and distinct errors (AC-012, AC-015, AC-019-021) | `tests/unit/test_configuration.py`, `tests/unit/test_ollama_client.py`, `tests/unit/test_prompt_contract.py`, `tests/integration/test_interpretation_api.py` |
| Privacy, no persistence, no external action, no telemetry (AC-013-016, AC-023) | `tests/unit/test_safety.py`, `tests/integration/test_interpretation_api.py` |
| Dataset distribution, mappings, scoring, thresholds, three-run gate, provenance/status behavior (AC-017-018, AC-022, AC-024) | `tests/evaluation/test_evaluation.py`, `src/reminder_agent/evaluation.py`, `.harness/run_evaluation.py` |
| Requirement-to-case coverage | `evals/dataset.json`; every case has at least one FR and AC mapping, and every FR/AC is linked to executable tests or evaluation checks in the matrix above |

## Current Verification Status

Offline test coverage and implementation checks are complete. Live-model evidence
remains pending until the configured Ollama server process has verified
`OLLAMA_NO_CLOUD=1`, the selected local model is verified in its inventory, and
all 57 genuine generations complete.
