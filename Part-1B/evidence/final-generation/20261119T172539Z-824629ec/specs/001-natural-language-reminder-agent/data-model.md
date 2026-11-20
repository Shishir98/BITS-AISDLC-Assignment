# Data Model: Natural-Language Reminder Agent

These are transient request/response models. None is a persisted reminder record.

## InterpretationRequest

| Field | Type | Constraints |
|---|---|---|
| `text` | string | Required, non-empty natural-language request. Treated as untrusted input. |
| `reference_datetime` | ISO-8601 datetime string | Required and timezone-aware; defines the reference instant for relative dates and future-time checks. |
| `timezone` | string | Required valid IANA timezone identifier; used for local calendar interpretation and echoed in the response. |

The reference datetime identifies an instant. Its offset is parsed as supplied;
local calendar interpretation is performed in `timezone`.

## InterpretationResult

| Field | Type | Constraints |
|---|---|---|
| `status` | enum | `ready`, `clarification_required`, or `unsupported`. |
| `intent` | enum | `create`, `reschedule`, `snooze`, or `unknown`. |
| `title` | string or null | Non-empty when present; required for a ready CREATE. |
| `scheduled_at` | ISO-8601 datetime or null | If present, timezone-aware with a numeric offset valid for `timezone` at that instant. |
| `timezone` | string | Valid IANA identifier; equals the request timezone. |
| `target_reference` | string or null | Non-empty when present; required for ready RESCHEDULE and SNOOZE. A textual reference only; it is not looked up in a reminder store. |
| `snooze_minutes` | integer or null | Positive whole number when present; required for ready SNOOZE. |
| `clarification_questions` | array of strings | Empty for ready/unsupported; at least one concise question for clarification. |
| `user_message` | string | Required, concise (1-240 characters), user-facing summary; contains no private reasoning. |

### State and Field Relationships

- `ready/create`: non-empty `title`; future `scheduled_at`; matching
  `timezone`; null `target_reference` and `snooze_minutes`; no clarification
  questions.
- `ready/reschedule`: non-empty `target_reference`; future `scheduled_at`;
  matching `timezone`; null `title` and `snooze_minutes`; no clarification
  questions.
- `ready/snooze`: non-empty `target_reference`; positive `snooze_minutes`;
  null `title` and `scheduled_at`; no clarification questions.
- `clarification_required`: at least one question; `scheduled_at` is null; never
  considered actionable. Known intent may be retained, or `unknown` used when the
  intent itself is unclear.
- `unsupported/unknown`: all action fields (`title`, `scheduled_at`,
  `target_reference`, and `snooze_minutes`) are null; no clarification questions.
- Every result has exactly the contract fields; no additional properties.

## Ollama Runtime Configuration

| Variable | Type | Constraints/default |
|---|---|---|
| `OLLAMA_BASE_URL` | URL | Defaults to `http://127.0.0.1:11434`; non-loopback must be explicitly configured and identified as outside normal local-only mode. |
| `OLLAMA_MODEL` | string | Defaults to `qwen3.5:9b`; configurable exact local model identifier, verified installed before evaluation. Never downloaded or substituted automatically. |
| `OLLAMA_TIMEOUT` | positive seconds | Defaults to 120 seconds. |
| `MODEL_TEMPERATURE` | finite number | Defaults to `0.2`; remains configurable and the actual effective value is recorded for every evaluation. |
| `MODEL_TOP_P` | finite number | Defaults to `0.9`; apply only where supported and record whether applied. |
| `MODEL_CONTEXT_LENGTH` | positive integer | Defaults to `4096`; record actual value and send as Ollama `num_ctx`. |

No model API key or cloud credential is required. Set `OLLAMA_NO_CLOUD=1` in the
Ollama server process environment and restart that process. Verify the setting in
the actual server process; the FastAPI process environment or localhost endpoint
alone is insufficient evidence.

The untrusted Ollama response is an ephemeral model candidate. It must pass all
`InterpretationResult` type, schema, and relationship checks before it can become a
successful API response. No model-specific transport metadata is exposed in the
public API result.

## ApplicationError

| Code | HTTP status | Meaning |
|---|---:|---|
| `INVALID_REQUEST` | 422 | The request envelope is invalid, such as an empty text, naive reference datetime, or invalid IANA timezone. Not a model/runtime failure. |
| `OLLAMA_UNAVAILABLE` | 503 | The configured local Ollama HTTP runtime cannot be reached. |
| `MODEL_NOT_INSTALLED` | 503 | The exact configured model is not installed locally or is identified as remote. |
| `INFERENCE_TIMEOUT` | 504 | Ollama did not complete inference within `OLLAMA_TIMEOUT`. |
| `INVALID_MODEL_OUTPUT` | 502 | The generated output cannot be parsed or violates schema/cross-field invariants. |
| `APPLICATION_ERROR` | 500 | An unexpected application failure occurred; no fabricated result is returned. |

## InstalledModelMetadata

The local model preflight obtains the configured model from Ollama's local model
list. Record the exact `model` identifier and `digest`, plus available `details`
such as format, family, parameter size, quantization level, and package details.
Reject missing models and entries marked with remote-model metadata.

## EvaluationCase

| Field | Type | Constraints |
|---|---|---|
| `case_id` | string | Stable unique identifier. |
| `category` | enum/string | One primary category: representative, boundary, ambiguous/missing, malformed, or adversarial/guardrail. |
| `text`, `reference_datetime`, `timezone` | string, ISO-8601 datetime, IANA string | Together form a valid `InterpretationRequest`; malformed-language cases still use a valid API envelope. |
| `fr_ids` | array of IDs | One or more `FR-###` references. |
| `ac_ids` | array of IDs | One or more `AC-###` references. |
| `expected` | object | Deterministic values for status, intent, title, time, target, and duration. |
| `ground_truth` | string | Explicit semantic reference for the expected interpretation. |
| `clarification_topics` | array | Explicit missing or ambiguous information the question must address when clarification is expected. |
| `required_value_weights` | object | Per-field points totaling 40 for required-value scoring; values are checked against `expected`. |
| `quality_requirements` | array | Measurable user-message or clarification checks for the 20-point quality rubric. |
| `property_assertions` | array | Named measurable, non-critical property assertions. |
| `critical_invariants` | array | Applicable safety gates; every applicable gate must pass. |
| `equivalence_group` | string or absent | Shared group ID for paraphrases; at least two groups have multiple cases. |

Dataset records contain no secrets or runtime environment values. Raw Ollama
generations are kept only as evaluation-run evidence; the application itself does
not persist requests or results.

## EvaluationEvidence

| Field | Type | Constraints |
|---|---|---|
| `ollama_version` | string | Version from the installed Ollama CLI/runtime. |
| `ollama_cloud_disabled` | boolean | Must be `true`; verified from the Ollama server process environment after restart, not inferred from the application environment or localhost URL. |
| `server_configuration_evidence` | object/reference | Records the method and evidence for verifying `OLLAMA_NO_CLOUD=1` in the actual Ollama server process. |
| `endpoint_mode` | enum | `loopback` or `non_loopback`; non-loopback requires explicit configuration and a visible warning. |
| `model_identifier` | string | Exact configured, locally installed model ID. |
| `model_digest` | string or null | Digest from Ollama model metadata when available. |
| `model_details` | object | Quantization, package, format, family, and parameter details where available. |
| `local_model_inventory_evidence` | object/reference | Actual Ollama `/api/tags` inventory evidence for the selected local model, including remote-metadata checks. |
| `prompt_version` | string | Version identifier embedded with the system prompt. |
| `prompt_digest` | SHA-256 string | Digest of the exact prompt bytes used. |
| `generation_parameters` | object | Actual effective temperature (default `0.2`), top-p (default `0.9`) status/value, context length (default `4096`), timeout, and all Ollama generation options. |
| `gpu_cpu_offload` | object | Actual `ollama ps` observation when available; records GPU-resident, CPU-resident, or partially offloaded. CPU fallback is an environment observation, not an application failure. |
| `dataset_digest` | SHA-256 string | Digest of the exact evaluation dataset bytes. |
| `reference_datetime` | ISO-8601 datetime string | Fixed per case and reused across the three runs. |
| `timezone` | string | Valid IANA timezone from the case. |
| `generations` | array of three run results | Three independent actual Ollama inference results, including generated output or distinct error code. |
| `observed_output_variation` | object | Exact-output distinct count and differing run indexes computed from the unchanged three actual outputs. |
| `expected_generation_count` | integer | Exactly 57 for the 19-case baseline. |
| `completed_generation_count` | integer | Actual number completed; fewer than 57 makes the baseline run incomplete. |
| `dataset_path` | string | `evals/dataset.json`; no duplicate JSONL dataset is used. |
| `evaluation_results_path` | string | `evidence/evaluations/<run-id>/eval-results.json`. |

The evaluation harness may persist this evidence, including actual model outputs,
under `Part-1B/evidence/evaluations/<run-id>/`. Unit-test fixtures or HTTP test
doubles must never be written as final evaluation evidence.
