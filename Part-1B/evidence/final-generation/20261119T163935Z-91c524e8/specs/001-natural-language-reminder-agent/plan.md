# Implementation Plan: Natural-Language Reminder Agent

**Branch**: `001-natural-language-reminder-agent` | **Date**: 2026-11-19
| **Spec**: [spec.md](spec.md)

**Input**: Feature specification from
`/specs/001-natural-language-reminder-agent/spec.md`

## Summary

Build a stateless FastAPI interpretation service that accepts reminder text plus
explicit temporal context, sends it to one locally installed model through
Ollama's local HTTP API, and independently validates the generated result with
Pydantic and standard timezone data before returning it. Cloud inference,
persistence, and external reminder actions are excluded.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: FastAPI, Pydantic, HTTPX, jsonschema, PyYAML, tzdata
for Windows IANA-zone data, pytest, Ruff, and the installed local Ollama model
`qwen3.5:9b` by default

**Dependency Management**: uv

**Storage**: None for the application; the evaluation harness may preserve actual
generation evidence under `evidence/evaluations/`

**Testing**: pytest; deterministic Ollama HTTP test double for unit/contract tests;
final evaluation against actual local-model inference only

**Target Platform**: Windows, Python 3.12 ASGI service, and local Ollama;
GPU offload is observed with `ollama ps`, while CPU fallback remains supported

**Project Type**: Single-project web service

**Performance Goals**: No numerical latency or throughput objective was supplied;
`OLLAMA_TIMEOUT` bounds an individual inference request.

**Constraints**: Strict response contract; explicit reference datetime and IANA
timezone; Ollama local HTTP API; local model only; `OLLAMA_NO_CLOUD=1` in the
Ollama server process environment followed by server restart; configurable
runtime/generation variables defaulting to `qwen3.5:9b`, temperature `0.2`,
top-p `0.9`, and context length `4096`; no cloud inference, API keys, telemetry,
remote logging, persistence, tools, scheduler, delivery, or user accounts.

**Scale/Scope**: One interpretation per request; no stateful reminder lifecycle.

## Architecture and Decisions

1. **HTTP boundary**: `POST /v1/reminders/interpret` accepts a validated request
   containing `text`, `reference_datetime`, and `timezone`.
2. **Local inference boundary**: `ollama_client.py` calls the configured Ollama
   local HTTP API. The default `OLLAMA_BASE_URL` is
   `http://127.0.0.1:11434`; no cloud inference service is called. User text is
   untrusted, and no model tools are sent.
3. **Structured generation and independent validation**: Pass the approved
   response JSON Schema to Ollama's chat `format` field where supported and
   include the schema requirements in a versioned system prompt. Parse every
   output with strict Pydantic models and enforce field relationships,
   timezone/offset validity, and temporal rules independently.
4. **Local model preflight**: Before evaluation, verify `OLLAMA_NO_CLOUD=1` in the
   restarted Ollama server process (not merely the FastAPI process), verify the
   exact `OLLAMA_MODEL` in the actual local model inventory (`/api/tags`), and
   reject remote model metadata. A localhost base URL alone does not prove
   cloud-disabled operation. An explicitly configured non-loopback endpoint emits
   a local warning and is recorded as outside normal local-only mode.
5. **Configuration**: `OLLAMA_MODEL` defaults to `qwen3.5:9b`.
   `OLLAMA_TIMEOUT` defaults to 120 seconds; `MODEL_TEMPERATURE` to `0.2`,
   `MODEL_TOP_P` to `0.9`, and `MODEL_CONTEXT_LENGTH` to `4096`. All are
   configurable; top-p is sent only where supported. No model API key or cloud
   credential is used.
6. **Error boundaries**: Map runtime unavailable, model not installed, inference
   timeout, invalid model output, and application errors to
   `OLLAMA_UNAVAILABLE`, `MODEL_NOT_INSTALLED`, `INFERENCE_TIMEOUT`,
   `INVALID_MODEL_OUTPUT`, and `APPLICATION_ERROR`, respectively.
7. **Stateless privacy**: The application does not persist requests/results or add
   telemetry, analytics, or remote logging. Only the evaluation harness writes
   actual generation evidence to `evidence/evaluations/`.

## Constitution Check

### Before Phase 0

- [x] Interpret/propose only; no reminder execution or persistence.
- [x] Python 3.12, FastAPI, Pydantic, uv, and local Ollama are within the requested
  boundary.
- [x] Default inference endpoint is loopback; cloud models and cloud inference are
  prohibited; no API key or cloud credential is used.
- [x] Strict output validation, explicit temporal context, fail-closed behavior,
  untrusted user input, disabled tools, and no private chain-of-thought are planned.
- [x] Evaluation thresholds and minimum dataset size are recorded before
  implementation.
- [x] No additional bootstrap, approval, trust-baseline, signing, or protected-runner
  infrastructure is included.

### After Phase 1 Design

- [x] API and data model preserve the proposal-only stateless boundary.
- [x] Contracts encode required fields, intent/status relationships, and distinct
  runtime error codes.
- [x] Evaluation artifacts define the scoring, safety gates, three actual runs per
  case, reproducibility metadata, and evidence location.
- [x] A locally installed model is the only model-specific runtime dependency.
- [x] Offline tests and Ruff checks passed; the verified live evaluation completed
  all 57 generations but failed the mandatory gates. Final verification remains
  open; see `traceability.md` for evidence and scores.

## Project Structure

```text
Part-1B/
├── pyproject.toml
├── uv.lock
├── README.md
├── .env.example
├── src/reminder_agent/
├── prompts/
│   └── system_prompt.md
├── tests/{api_contract,unit,integration,evaluation}/
├── evals/dataset.json
├── .harness/run_evaluation.py
├── scripts/start-ollama-local.ps1
└── evidence/
    ├── initial-generation/
    ├── final-generation/
    ├── evaluations/<run-id>/
    └── failures/
```

The evaluation dataset is only `evals/dataset.json`; the integrated harness has
only `.harness/run_evaluation.py` as its primary command. Reusable scoring and
validation logic is in `src/reminder_agent/evaluation.py`. Feature design and
acceptance artifacts remain under `specs/001-natural-language-reminder-agent/`.

## Design Artifacts

- [`research.md`](research.md): Ollama design decisions and official API references.
- [`data-model.md`](data-model.md): request, result, and evaluation evidence models.
- [`contracts/interpretation.openapi.yaml`](contracts/interpretation.openapi.yaml):
  public API and strict JSON response schema.
- [`evaluation-strategy.md`](evaluation-strategy.md): dataset, scoring, provenance,
  and infrastructure/semantic result handling.
- [`traceability.md`](traceability.md): requirement/criterion/evaluation mapping.
- [`quickstart.md`](quickstart.md): implementation-phase local validation sequence.

## Implementation Milestones

1. **M1 - Project and contract foundation**: Establish the Python 3.12/uv project,
   Ollama environment configuration, strict Pydantic request/result types, and
   deterministic HTTP-client unit tests. No application code is created as part
   of this SDD task.
2. **M2 - Temporal and domain rules**: Implement intent/result validation,
   timezone handling, explicit reference-time semantics, and fail-closed temporal
   behavior.
3. **M3 - CREATE vertical slice**: Implement and verify the `ready/create` and
   CREATE clarification paths.
4. **M4 - RESCHEDULE and SNOOZE**: Implement and verify both remaining supported
   intent paths and their missing-information cases.
5. **M5 - Safe API and local runtime integration**: Add the interpretation
   endpoint, Ollama chat client, JSON Schema structured output, schema-bearing
   versioned prompt, local model preflight, safety boundaries, and distinct
   failures.
6. **M6 - Evaluation harness**: Create `evals/dataset.json` with the 19-case
   baseline distribution and full traceability; implement the single integrated
   runner at `.harness/run_evaluation.py`; verify server-process cloud configuration
   and actual local model inventory; execute three independent actual inference
   runs per case (57 generations); record required metadata, genuine output
   variation, and generations in assignment evidence.
7. **M7 - Final verification**: Run contract, behavior, and safety checks plus
   actual-model evaluation; distinguish infrastructure errors from semantic
   failures; record scores without changing thresholds; update quickstart and
   traceability evidence.

## Complexity Tracking

No constitution violations or additional architectural components are proposed.
