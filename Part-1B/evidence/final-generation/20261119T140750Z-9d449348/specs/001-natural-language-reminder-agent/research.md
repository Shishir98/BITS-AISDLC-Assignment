# Research and Design Decisions

**Feature**: [Natural-Language Reminder Agent](spec.md)
**Date**: 2026-11-19

## Decisions

### D1 - Use the owner-mandated small Python service stack

- **Decision**: Python 3.12, FastAPI, Pydantic, and uv.
- **Rationale**: These are explicit constraints in the feature brief; no stack
  comparison is needed.
- **Alternatives considered**: None; selecting another stack would violate scope.

### D2 - Use local Ollama inference only

- **Decision**: Send reminder text to Ollama's local HTTP API, defaulting to
  `http://127.0.0.1:11434`, with `qwen3.5:9b` as the configurable default local
  model. Set
  `OLLAMA_NO_CLOUD=1` in the Ollama server process environment and restart that
  process; verify the process setting and actual local model inventory during
  evaluation. A localhost application URL alone is not evidence that cloud
  features are disabled. Reject remote model metadata.
- **Rationale**: This meets the owner's local inference and privacy requirements.
  Ollama documents local API use, cloud feature disabling, and remote model
  metadata.
- **Alternatives considered**: Cloud inference and cloud models are prohibited.

### D3 - Use Ollama JSON Schema structured output, then validate independently

- **Decision**: Pass the approved response schema through Ollama's chat `format`
  field where supported and include the same requirements in the system prompt.
  Parse the generated result with strict Pydantic models and application
  cross-field validation.
- **Rationale**: Ollama's structured-output documentation recommends schema
  generation and Pydantic parsing; constrained output does not guarantee
  application-level temporal or semantic invariants.
- **Alternatives considered**: Relying on prompt-only JSON or trusting generated
  schema-constrained output without validation was rejected.

### D4 - Verify and identify the installed local model

- **Decision**: Before evaluation, check Ollama `/api/tags` for the exact
  configured model. Record its identifier, digest, and available model details;
  reject missing models or entries marked with `remote_model`/`remote_host`.
- **Rationale**: The local model endpoint exposes available model metadata,
  including digest and quantization details where available.
- **Alternatives considered**: Guessing a model identifier or silently substituting
  another model was rejected.

### D5 - Preserve actual, reproducible evaluation outputs

- **Decision**: Run each case three independent times using identical recorded
  inputs and generation settings. Record Ollama version, model metadata, prompt
  and dataset digests, fixed temporal inputs, effective options, and each actual
  generation under `evidence/evaluations/`.
- **Rationale**: This preserves repeatability and evaluates real model behavior
  without manufacturing variation or treating test fixtures as evidence.
- **Alternatives considered**: Mocked final outputs and changing parameters
  between repetitions were rejected.

### D6 - Keep the application stateless and private

- **Decision**: Do not persist application requests/results or add telemetry,
  analytics, or remote logging. Only the evaluation harness writes actual model
  outputs as assignment evidence.
- **Rationale**: The service interprets and proposes; it has no reminder lifecycle.
- **Alternatives considered**: Persistent application logs/results or external
  analytics are outside the product boundary.

## Verified Ollama References

- [Chat API](https://docs.ollama.com/api/chat): local `/api/chat`, non-streaming
  requests, JSON Schema `format`, and generation options.
- [Structured Outputs](https://docs.ollama.com/capabilities/structured-outputs):
  schema passed to `format`, schema requirements in prompt, and Pydantic
  validation.
- [List Models API](https://docs.ollama.com/api/tags): locally available model
  identifiers, digest, model details, and remote model metadata.
- [Ollama Cloud and Local Mode](https://docs.ollama.com/cloud) and
  [Local FAQ](https://docs.ollama.com/faq#how-do-i-disable-ollama-cloud-features):
  cloud inference behavior and `OLLAMA_NO_CLOUD=1`.

## Runtime Configuration

`OLLAMA_BASE_URL` defaults to `http://127.0.0.1:11434`. `OLLAMA_MODEL` is the
configurable installed local model identifier and defaults to `qwen3.5:9b`.
`OLLAMA_TIMEOUT` defaults to 120 seconds; `MODEL_TEMPERATURE` defaults to `0.2`;
`MODEL_TOP_P` defaults to `0.9`; and `MODEL_CONTEXT_LENGTH` defaults to `4096`.
All are configurable; top-p is sent only where supported and context length is
sent as `num_ctx`. No model API key or cloud credential is used. A
The application uses Python's standard `zoneinfo` API. Windows installations
without an operating-system IANA timezone database require the pinned `tzdata`
dependency so IANA validation and daylight-saving transition checks are
available consistently. A non-loopback endpoint must be explicitly configured
and visibly marked outside normal local-only mode.

## Remaining Deployment Value

The exact local model identifier is not fixed in the brief because it depends on
the installed model. Set `OLLAMA_MODEL` to the chosen local model and verify it is
installed before evaluation. Installation of the selected local model is the only
model-specific deployment dependency.
