# Requirements and Evaluation Traceability

The single evaluation dataset `evals/dataset.json` is created during the harness
phase and evaluated by `.harness/run_evaluation.py`. Every case must include at
least one FR and AC identifier; final actual generation evidence is stored under
`evidence/evaluations/<run-id>/`.

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

## Task Traceability

Task IDs identify planned implementation and verification work. During
implementation, update this matrix with actual test/evidence references; an AC is
covered only when an executable check verifies its stated outcome.
