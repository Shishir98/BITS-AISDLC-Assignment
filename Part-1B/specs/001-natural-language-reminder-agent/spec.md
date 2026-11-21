# Feature Specification: Natural-Language Reminder Agent

**Feature Branch**: `001-natural-language-reminder-agent`

**Created**: 2026-11-19

**Status**: Implemented; actual-model evaluation completed with PASS

**Input**: Build a small AI-powered service that interprets unstructured reminder
requests and returns structured proposed actions; do not schedule or execute them.

## Purpose and Scope

The service accepts one reminder-related request and returns either a complete
proposed CREATE, RESCHEDULE, or SNOOZE action; a clarification request; or an
UNSUPPORTED result. It interprets meaning across varied wording rather than relying
on exact phrase matching.

The service is stateless and has no reminder store. It does not schedule, deliver,
or execute reminders. Calendar, messaging, email, notification, authentication,
user-management, database, queue, scheduler, and frontend functionality are out of
scope.

## Local Inference Architecture

Inference runs through the Ollama local HTTP API using one locally installed model.
The default endpoint is `http://127.0.0.1:11434`; cloud models and cloud inference
are prohibited. `OLLAMA_MODEL` defaults to `qwen3.5:9b` and may be configured to
another locally installed model. Configure `OLLAMA_BASE_URL`, `OLLAMA_MODEL`,
`OLLAMA_TIMEOUT`, `MODEL_TEMPERATURE`, `MODEL_TOP_P`, and
`MODEL_CONTEXT_LENGTH` through environment variables. No API key or cloud
credential is required.

`OLLAMA_TIMEOUT` defaults to 120 seconds and must be positive.
`MODEL_TEMPERATURE` defaults to `0.2`. `MODEL_TOP_P` defaults to `0.9` and is sent
only when supported. `MODEL_CONTEXT_LENGTH` defaults
to `4096`. All effective values are recorded for evaluation. A non-loopback base
URL must be explicitly configured and clearly identified as outside the normal
local-only operating mode.

Set `OLLAMA_NO_CLOUD=1` in the Ollama server process environment and restart the
server. Before evaluation, verify that setting in the actual server process and
verify the selected model against Ollama's actual local model inventory; reject
remote model metadata. A localhost `OLLAMA_BASE_URL` alone does not verify that
cloud features are disabled. The application sends reminder text only to this
configured Ollama endpoint and adds no telemetry, analytics, or remote logging.

## User Scenarios & Testing

### User Story 1 - Propose a New Reminder (Priority: P1)

As a person making a reminder request, I want the service to extract its description,
date, and exact time so I can review a complete proposed reminder.

**Why this priority**: Creating a proposed reminder is the primary product value and
the smallest useful end-to-end increment.

**Independent Test**: Submit representative and paraphrased CREATE requests with a
fixed reference datetime and timezone; verify complete requests return a valid
`ready/create` response and incomplete requests do not.

**Acceptance Scenarios**:

1. **Given** a non-empty reminder description and an unambiguous future date and
   exact time, **When** the person asks to be reminded in natural language,
   **Then** the response is `ready/create` with the extracted title and
   timezone-aware scheduled datetime. (AC-001, AC-002)
2. **Given** either the description or exact time is absent or materially ambiguous,
   **When** the request is interpreted, **Then** the response is
   `clarification_required` and does not contain a scheduled datetime. (AC-003)
3. **Given** the same meaning expressed with different wording, **When** both
   requests are evaluated against the same reference datetime and timezone,
   **Then** their intent and required extracted values are equivalent. (AC-001)

### User Story 2 - Propose a Reminder Change (Priority: P2)

As a person changing a reminder, I want the service to distinguish rescheduling from
snoozing and capture the target and requested new time or duration.

**Why this priority**: Reschedule and snooze are the other supported actionable
operations; both depend on identifying an existing reminder by a textual reference.

**Independent Test**: Submit complete and incomplete RESCHEDULE and SNOOZE requests
with fixed temporal context; verify their intent-specific fields and clarification
behavior.

**Acceptance Scenarios**:

1. **Given** a target reference and an unambiguous future new date and time,
   **When** the person requests a move or reschedule, **Then** the response is
   `ready/reschedule` with the target and new scheduled datetime. (AC-004)
2. **Given** a target reference and a positive whole-number snooze duration,
   **When** the person requests a snooze, **Then** the response is `ready/snooze`
   with the target and duration in minutes. (AC-005)
3. **Given** a missing target, missing new time, or missing/invalid snooze duration,
   **When** the request is interpreted, **Then** the response requests clarification
   and is not actionable. (AC-006)

### User Story 3 - Resolve Ambiguity and Reject Unsupported Requests (Priority: P1)

As a person whose request is incomplete, ambiguous, malformed, or outside reminder
operations, I want a clear safe response rather than an invented or executed action.

**Why this priority**: Safe non-actionable outcomes are mandatory for every intent
and prevent the model from turning uncertainty into a commitment.

**Independent Test**: Submit missing-field, ambiguous-time, past-time, malformed,
unsupported, and adversarial inputs; verify clarification or unsupported outcomes
and all safety invariants.

**Acceptance Scenarios**:

1. **Given** a recognizable supported intent with missing mandatory information,
   **When** it is interpreted, **Then** the result is `clarification_required` with
   at least one concise question and no scheduled datetime. (AC-003, AC-006)
2. **Given** a request clearly outside CREATE, RESCHEDULE, and SNOOZE,
   **When** it is interpreted, **Then** the result is `unsupported/unknown` with
   every actionable field null. (AC-007)
3. **Given** user text that attempts to override instructions, request private
   reasoning, or trigger a tool/action, **When** it is interpreted, **Then** the
   text remains untrusted data and cannot override policy, trigger a tool call,
   or expose private reasoning. (AC-013, AC-014)

## Acceptance Criteria

- **AC-001**: Semantically equivalent supported requests under the same temporal
  context produce the same intent and equivalent required values, regardless of
  wording; exact phrase matching alone does not satisfy this criterion.
- **AC-002**: A ready CREATE has a non-empty title, a timezone-aware
  `scheduled_at` strictly later than the supplied reference instant, matching
  timezone, null target and snooze fields, and an empty clarification array.
- **AC-003**: CREATE without a non-empty description or exact unambiguous time, or
  with an ambiguous request, returns clarification; it never becomes ready.
- **AC-004**: A ready RESCHEDULE has a non-empty target reference and future
  timezone-aware new `scheduled_at`, matching timezone, null title and snooze
  fields, and an empty clarification array.
- **AC-005**: A ready SNOOZE has a non-empty target reference and positive integer
  `snooze_minutes`, with null title and scheduled datetime and an empty
  clarification array.
- **AC-006**: Missing mandatory RESCHEDULE or SNOOZE information, including a
  missing target, new time, or positive duration, returns clarification and never
  a ready response.
- **AC-007**: A clearly unsupported operation returns `unsupported/unknown`;
  title, scheduled datetime, target reference, and snooze duration are null and
  clarification questions are empty.
- **AC-008**: Every successful interpretation has exactly the documented response
  fields and types; unknown fields, invalid enums, malformed datetimes, naive
  datetimes, and invalid field relationships are rejected.
- **AC-009**: The response timezone is a valid IANA identifier and equals the
  request timezone. Any non-null scheduled datetime carries the offset valid for
  that timezone at the scheduled instant.
- **AC-010**: Relative date interpretation uses the request's explicit reference
  datetime and timezone, never the host clock or a hidden default.
- **AC-011**: A past or equal-to-reference requested instant, nonexistent local
  time, or ambiguous repeated local time cannot return a ready action; it requires
  clarification. The service never silently shifts a past time or chooses a DST
  fold.
- **AC-012**: Ollama-generated output is independently parsed and checked against
  the schema and cross-field rules. Invalid or inconsistent output cannot be
  returned as ready; runtime failures return a distinct non-success error, not a
  success-shaped fallback.
- **AC-013**: Adversarial instructions in user text do not override system
  instructions, fabricate missing details, change the allowed intent set, or
  elicit private chain-of-thought.
- **AC-014**: No model tool/action call or external reminder action occurs; the
  service returns proposed data only.
- **AC-015**: `OLLAMA_BASE_URL` defaults to `http://127.0.0.1:11434`;
  `OLLAMA_MODEL` defaults to `qwen3.5:9b` and identifies the installed local model;
  `OLLAMA_TIMEOUT` defaults to 120 positive seconds; `MODEL_TEMPERATURE` defaults
  to `0.2`; `MODEL_TOP_P` defaults to `0.9`; and `MODEL_CONTEXT_LENGTH` defaults
  to `4096`. All remain configurable, and no model API key or cloud credential is
  required, read, stored, or logged.
- **AC-016**: Interpretation leaves no persisted request, reminder, or model
  result; the service has no reminder persistence or delivery behavior.
- **AC-017**: The evaluation set contains at least 19 meaningful unique cases;
  the 19-case baseline has exactly 5 representative, 4 boundary, 4
  ambiguous/missing, 2 malformed-language, and 4 adversarial/guardrail cases.
  Every case has expected fields or a semantic rubric and maps to at least one
  requirement ID and one acceptance-criterion ID. Each case is run three
  independent times against the actual installed local model; a complete
  successful baseline run contains exactly 57 actual generations. Final evidence
  contains no mocked outputs, and any runtime/infrastructure call failure makes
  the run incomplete rather than a successful 57-generation run. The dataset is
  stored at `evals/dataset.json` and the single integrated harness entry point is
  `.harness/run_evaluation.py`.
- **AC-018**: Evaluation is PASS only if structural validation is 100%, critical
  safety invariants are 100%, property/invariant score is at least 95%, semantic/
  quality score is at least 85%, and the unrounded weighted aggregate is at least
  90%, where Aggregate = 0.30 × Structural + 0.35 × Property/Invariant +
  0.35 × Semantic/Quality.
- **AC-019**: Evaluation preflight verifies Ollama is reachable, `OLLAMA_NO_CLOUD=1`
  is set in the Ollama server process environment (not merely the FastAPI
  environment), Ollama was restarted after the setting was applied, and the exact
  `OLLAMA_MODEL` appears in the actual local model inventory without remote-model
  metadata. Evidence records the server-process configuration and local inventory;
  a localhost `OLLAMA_BASE_URL` alone is insufficient to claim verified local-only
  operation. A non-loopback `OLLAMA_BASE_URL` is accepted only when explicitly
  configured and is identified as outside normal local-only mode.
- **AC-020**: The Ollama chat request passes the approved response JSON Schema
  through structured output when supported and includes the schema requirements
  in the system prompt. The application independently validates every result with
  Pydantic and cross-field rules; model tools are disabled.
- **AC-021**: Failures use distinct codes: `OLLAMA_UNAVAILABLE`,
  `MODEL_NOT_INSTALLED`, `INFERENCE_TIMEOUT`, `INVALID_MODEL_OUTPUT`, and
  `APPLICATION_ERROR`. Infrastructure/runtime failures are reported separately
  from semantic evaluation failures and never produce a fabricated success.
  Invalid request envelopes use `INVALID_REQUEST` with HTTP 422, distinct from
  runtime failures.
- **AC-022**: Each evaluation evidence run records Ollama version, exact model
  identifier, model digest and available quantization/package details, prompt
  version and digest, effective generation parameters including context length,
  dataset digest, each
  case's fixed reference datetime and timezone, and all three individual
  generation results. It records exact-output variation observed across the
  three genuine outputs without modifying or manufacturing variation.
- **AC-023**: The application does not transmit reminder text to cloud inference,
  add telemetry/analytics/remote logging, or persist requests/results. The
  evaluation harness may preserve actual model outputs under Part-1B
  `evidence/evaluations/`.
- **AC-024**: An infrastructure failure or incomplete set of three generations
  marks the evaluation as blocked/incomplete and cannot produce scores or PASS.
  `INVALID_MODEL_OUTPUT` is recorded as a structural evaluation failure.

## Requirements

### Functional Requirements

- **FR-001**: The service MUST accept one natural-language request, a timezone-aware
  reference datetime, and an IANA timezone, then return one structured interpretation.
- **FR-002**: The service MUST classify request meaning into CREATE, RESCHEDULE,
  SNOOZE, clarification, or unsupported outcomes; wording variation MUST NOT require
  exact phrase matches.
- **FR-003**: A ready CREATE MUST contain a non-empty title and a future exact
  scheduled datetime. Missing description, exact time, or material clarity MUST
  require clarification.
- **FR-004**: A ready RESCHEDULE MUST contain a target reference and an unambiguous
  future new scheduled datetime. Missing either MUST require clarification.
- **FR-005**: A ready SNOOZE MUST contain a target reference and positive integer
  snooze duration in minutes. Missing or invalid information MUST require
  clarification.
- **FR-006**: Clarification responses MUST identify the known or unknown intent,
  ask at least one concise question, and MUST NOT be treated as actionable.
- **FR-007**: Clearly unsupported requests MUST return `unsupported` with `unknown`
  intent and no actionable fields or invented supported intent.
- **FR-008**: The successful response MUST conform exactly to the strict JSON
  response contract in `contracts/interpretation.openapi.yaml`, including all
  required fields and cross-field constraints.
- **FR-009**: The service MUST use the explicit reference datetime and supplied
  timezone for relative dates, validate IANA timezone identifiers, and reject
  past, nonexistent, or unresolved ambiguous local times as actionable proposals.
- **FR-010**: The service MUST independently validate Ollama-generated results;
  invalid output MUST fail closed and MUST NOT be represented as a ready result.
- **FR-011**: The model interaction MUST treat user text as untrusted, disable
  external tool/action execution, and return no private chain-of-thought.
- **FR-012**: Ollama MUST be the sole inference runtime, using its local HTTP API
  with one locally installed model configured through environment variables;
  defaults MUST be `qwen3.5:9b`, `MODEL_TEMPERATURE=0.2`, `MODEL_TOP_P=0.9`, and
  `MODEL_CONTEXT_LENGTH=4096`; no model API key or cloud credential is required.
- **FR-013**: The service MUST NOT persist reminders or execute scheduling,
  notification, calendar, email, messaging, or other external actions.
- **FR-014**: The evaluation MUST use at least 19 traceable cases and apply the
  immutable pre-implementation thresholds and scoring method in
  `evaluation-strategy.md`; the dataset is `evals/dataset.json`, executed only by
  `.harness/run_evaluation.py`.
- **FR-015**: The service MUST default to the loopback Ollama endpoint, verify that
  the configured model is locally installed, reject remote model metadata, and
  clearly identify an explicitly configured non-loopback endpoint as outside
  normal local-only mode.
- **FR-016**: The service MUST pass the approved JSON Schema to Ollama structured
  output when supported, include schema requirements in the system prompt, and
  independently validate every result with Pydantic.
- **FR-017**: The evaluation harness MUST run each case three independent times
  against actual local-model inference and preserve the specified reproducibility
  metadata and individual generations in assignment evidence.
- **FR-018**: The application MUST NOT transmit reminder text to cloud inference,
  add telemetry, analytics, or remote logging, or persist requests/results.

### Response Contract Summary

The response fields are `status`, `intent`, `title`, `scheduled_at`, `timezone`,
`target_reference`, `snooze_minutes`, `clarification_questions`, and `user_message`.
The allowed status values are `ready`, `clarification_required`, and `unsupported`.
The allowed intent values are `create`, `reschedule`, `snooze`, and `unknown`.
The complete JSON Schema and field relationships are in
[`contracts/interpretation.openapi.yaml`](contracts/interpretation.openapi.yaml).

### Key Entities

- **Interpretation Request**: User text, explicit timezone-aware reference
  datetime, and IANA timezone; it exists only for the duration of a request.
- **Interpretation Result**: Strictly validated proposed action, clarification, or
  unsupported response; it is not a persisted reminder.
- **Evaluation Case**: Harness input plus deterministic ground truth or semantic
  rubric, mapped to requirement and acceptance criterion identifiers.

## Edge Cases

- A CREATE request such as "Remind me tomorrow" lacks a title; "Remind me to call
  Rahul" lacks an exact time. Both require clarification.
- A request with a past time, including "today at 5 PM" when 5 PM has passed,
  requires clarification; the time is not moved to tomorrow.
- A bare weekday resolves to the next occurrence strictly after the reference
  local date; if the request says "this <weekday>", it resolves within the current
  local week only when that date is not past. Otherwise clarification is required.
- A nonexistent or repeated local wall time during a daylight-saving transition
  requires clarification unless the request itself disambiguates the instant.
- An invalid timezone or timezone-naive reference datetime is rejected as invalid
  request input before interpretation.
- A malformed or empty request cannot produce a ready action.
- If Ollama is unavailable, the model is missing, inference times out, model
  output is invalid, or the application fails, the request returns the corresponding
  distinct error code; no fallback ready response is synthesized.
- Instructions embedded in user text to ignore rules, expose reasoning, or invoke
  tools are not followed.

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% of evaluation outputs pass structural validation.
- **SC-002**: 100% of critical safety invariants pass; any single failure makes the
  complete evaluation FAIL.
- **SC-003**: Overall property/invariant score is at least 95%.
- **SC-004**: Semantic/quality score is at least 85%.
- **SC-005**: Weighted aggregate is at least 90%, calculated without intermediate
  rounding as `0.30 × Structural + 0.35 × Property/Invariant + 0.35 ×
  Semantic/Quality`.
- **SC-006**: The evaluation dataset contains at least 19 meaningful cases across
  representative, boundary, ambiguous/missing, malformed, and adversarial/
  guardrail categories, with full requirement/acceptance-criterion traceability.
  The 19-case baseline distribution is 5/4/4/2/4 respectively; its complete
  successful evaluation contains exactly 57 actual generations.
- **SC-007**: The overall result is PASS only when all criteria SC-001 through
  SC-006 and all mandatory per-case safety gates pass. Thresholds are not adjusted
  after implementation begins.

The calculation rules and case distribution are specified in
[`evaluation-strategy.md`](evaluation-strategy.md).

## Clarifications

### Session 2026-11-19

- No product-scope question remained unanswered in the supplied description.
  Operational rules derived from the description are recorded in
  [`clarifications.md`](clarifications.md); the exact local model identifier is a
  deployment configuration value and must be installed before evaluation.

## Assumptions

- Each API request supplies its own reference datetime and timezone; neither is
  inferred from server settings or user profiles.
- For a bare weekday, the next occurrence is strictly after the reference local
  date. Explicit "this <weekday>" means the same local week, only if not past.
- Clarification results may preserve known intent and ask for missing details but
  never carry a scheduled datetime.
- The exact Ollama model identifier is selected through `OLLAMA_MODEL` and is
  `qwen3.5:9b` by default and is installed locally before evaluation. Unit tests may use an Ollama HTTP test
  double, but final evaluation evidence always comes from actual model inference.
- Evaluation evidence is written only by the harness under
  `evidence/evaluations/`; the running application does not persist requests or
  results.
- No request or interpretation is retained after its response.
