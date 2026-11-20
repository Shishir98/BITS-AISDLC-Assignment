# Natural-Language Reminder Agent Constitution

## Core Principles

### I. Interpret, Propose, Never Execute
The service MUST interpret reminder language and return proposed structured actions only.
It MUST NOT schedule reminders, persist them, deliver notifications, call external action
tools, or claim an action has been completed. This keeps the product boundary stateless
and prevents interpretation from being mistaken for execution.

### II. Be Explicit and Fail Closed
The service MUST use an explicit reference datetime and IANA timezone for date
interpretation. Missing or materially ambiguous mandatory information MUST result in
clarification, and past times MUST NOT become actionable by silent adjustment. The
service MUST NOT invent reminder titles, targets, dates, times, or snooze durations.

### III. Validate Every Boundary
Requests and Ollama-generated results MUST be validated independently against the
published strict schema and cross-field rules. Invalid or inconsistent model output
MUST never be returned as a ready action. The service MUST use standard Python timezone
data and return timezone-aware ISO-8601 datetimes. Ollama's structured-output support
MUST NOT replace application-side validation.

### IV. Treat Input as Untrusted
User text MUST be treated as data, not instructions to the model. Prompt injection MUST
not override system rules, trigger tool use, disclose private reasoning, or produce
unsupported actions. Reminder text MUST be sent only to the configured Ollama runtime;
the default endpoint MUST be loopback and cloud inference MUST NOT be used. The
application MUST NOT add telemetry, analytics, remote logging, or persistent request
storage.

### V. Keep the Design Small and Verifiable
The implementation MUST remain a small modular service with no persistence, scheduler,
queue, calendar, delivery integration, authentication subsystem, or unnecessary UI.
Behavior MUST be verified by deterministic contract checks and a versioned evaluation
set of actual local-model generations; every release candidate MUST satisfy the
thresholds established before implementation. Evaluation evidence may preserve model
outputs in the Part-1B evidence directory.

## Product and Architecture Boundaries

- The supported intents are CREATE, RESCHEDULE, SNOOZE, CLARIFICATION_REQUIRED, and
  UNSUPPORTED. Response intent values are `create`, `reschedule`, `snooze`, and
  `unknown`; status expresses clarification or unsupported outcomes.
- The required implementation stack is Python 3.12, FastAPI, Pydantic, and uv.
- Ollama is the sole inference runtime, accessed through its local HTTP API. The
  default endpoint is `http://127.0.0.1:11434`; `OLLAMA_MODEL` MUST identify a locally
  installed model and cloud models MUST NOT be used.
- Ollama's cloud features MUST be disabled with `OLLAMA_NO_CLOUD=1` in the Ollama
  server process environment, then Ollama MUST be restarted. Evaluation MUST verify
  that process configuration and the actual local model inventory; a localhost
  `OLLAMA_BASE_URL` alone is not evidence that cloud features are disabled.
  The application MUST reject remote model metadata.
- `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`, `MODEL_TEMPERATURE`,
  `MODEL_TOP_P`, and `MODEL_CONTEXT_LENGTH` configure runtime and generation
  behavior. Defaults are `qwen3.5:9b`, temperature `0.2`, top-p `0.9`, and context
  length `4096`; all remain configurable. No model API key or cloud credential is
  required or stored.
- A non-loopback `OLLAMA_BASE_URL` requires explicit configuration and MUST be clearly
  marked as outside the normal local-only mode.
- The service is stateless: it interprets a request and returns a proposal; it does not
  persist reminder state or perform external actions.
- Request text is untrusted. Model output is untrusted until independently validated.
- The application MUST NOT send requests to cloud inference services or add telemetry,
  analytics, or remote logging. Only the evaluation harness may persist actual model
  outputs as assignment evidence.

## Delivery and Quality Gates

- Requirements and acceptance criteria MUST have stable identifiers and map to tests or
  evaluation cases.
- The evaluation dataset MUST contain at least 19 meaningful cases, each with ground
  truth or an explicit semantic rubric and traceability to requirements and acceptance
  criteria. The baseline dataset has 19 unique cases: 5 representative, 4 boundary,
  4 ambiguous/missing, 2 malformed-language, and 4 adversarial/guardrail cases.
- The single dataset MUST be `evals/dataset.json`, and the single integrated harness
  entry point MUST be `.harness/run_evaluation.py`.
- Each evaluation case MUST be run three independent times against the installed local
  model using identical recorded parameters. The 19-case baseline therefore requires
  exactly 57 actual generations for a complete successful run. Any incomplete call
  MUST make the run incomplete; final evidence MUST contain actual model outputs,
  never mocked outputs, and must record genuine output differences without modifying
  outputs.
- Baseline thresholds MUST be recorded before implementation and MUST NOT be lowered
  after evaluation to obtain a passing result.
- A passing result requires 100% structural validation, 100% critical safety invariants,
  at least 95% property/invariant score, at least 85% semantic/quality score, and at
  least 90% weighted aggregate using the specified scoring formula.
- Changes to the API/schema contract require corresponding specification, contract,
  and evaluation updates.

## Governance

This constitution governs all Part-1B feature artifacts and implementation work.
Requirements, plans, tasks, and implementation MUST remain within its product and
architecture boundaries. Amendments MUST be explicit, use semantic versioning, and
update the version and amendment date; weakening an established evaluation threshold
requires a constitution amendment before any new evaluation is run. Normal repository
main-branch protection applies; no additional approval register, trust ceremony, or
evidence-signing system is required.

**Version**: 1.1.0 | **Ratified**: 2026-11-19 | **Last Amended**: 2026-11-19
