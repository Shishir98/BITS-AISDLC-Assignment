# Natural-Language Reminder Agent

A stateless FastAPI service that interprets reminder requests and returns
validated proposals. It does not persist, schedule, deliver, or execute
reminders. Inference uses one locally installed model through Ollama's local
HTTP API; requests are not sent to cloud AI providers.

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Ollama with the configured model installed locally (default: `qwen3.5:9b`)

Before evaluation, disable Ollama cloud features in the **Ollama server
process**, then restart that process with `OLLAMA_NO_CLOUD=1`. For a controlled
PowerShell launch, see `scripts/start-ollama-local.ps1`. A localhost URL or a
variable set only in the FastAPI process does not verify the Ollama server
configuration. Check `ollama list` and the server's `/api/tags` inventory for
the exact local model. Install the selected model explicitly if needed, for
example `ollama pull qwen3.5:9b`; the application never downloads or substitutes
a model.

## Configure and run

From `Part-1B/`:

```powershell
uv sync --locked
$env:OLLAMA_BASE_URL = 'http://127.0.0.1:11434'
$env:OLLAMA_MODEL = 'qwen3.5:9b'
$env:OLLAMA_TIMEOUT = '120'
$env:MODEL_TEMPERATURE = '0.2'
$env:MODEL_TOP_P = '0.9'
$env:MODEL_CONTEXT_LENGTH = '4096'
uv run uvicorn reminder_agent.api:app --app-dir src --host 127.0.0.1 --port 8000
```

Configuration is also documented in `.env.example`; credentials are not used.
The default endpoint is loopback. A non-loopback endpoint is explicitly warned
about and is outside normal local-only operation.
Chat requests set Ollama's supported `think` control to `false` so internal
reasoning does not consume the structured response context. This does not change
the configured temperature, top-p, context length, or timeout; the setting is
recorded in each evaluation manifest.

The service provides the model with deterministic reference-time and DST
analysis, then independently checks the returned data. Supplied titles and
targets must be grounded in normalized contiguous request text, with limited
verb equivalence; unsupported paraphrases can therefore be rejected rather
than guessed. An explicitly requested first or second repeated-time occurrence
may select that DST fold; otherwise repeated times require clarification.

## Validation and evaluation

```powershell
uv run pytest
uv run ruff check src tests .harness
uv run python .harness/run_evaluation.py
```

The baseline `evals/dataset.json` contains 19 cases. A complete evaluation makes
three independent genuine Ollama calls per case (57 calls, with no retries).
Empty, truncated, or invalid model output is scored as a failure, not a
successful interpretation.
Infrastructure failures make the run incomplete. Test doubles are used only by
offline tests and never as evaluation evidence. The harness records actual model
outputs and provenance under `evidence/evaluations/`, including HTTP response
metadata and the response body with private thinking redacted and hashed. It
does not manufacture variation or lower any approved threshold.

The assignment evidence includes [the harness log](evidence/harness-log.md) and
[the selected evaluation result](evidence/eval-results.json). The latter is a
copy of the run identified in the log; after a new run, explicitly refresh the
copy and log while retaining the original run-specific evidence.
`evidence/harness.log` is a plain-text copy of the same log and should be
refreshed whenever the Markdown log changes.

See [the quickstart](specs/001-natural-language-reminder-agent/quickstart.md)
and [evaluation strategy](specs/001-natural-language-reminder-agent/evaluation-strategy.md)
for local-runtime verification, scoring gates, and evidence requirements.
