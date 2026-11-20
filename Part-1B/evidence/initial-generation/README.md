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

## Validation and evaluation

```powershell
uv run pytest
uv run ruff check src tests .harness
uv run python .harness/run_evaluation.py
```

The baseline `evals/dataset.json` contains 19 cases. A complete evaluation makes
three independent genuine Ollama generations per case (57 successful calls).
Infrastructure failures make the run incomplete. Test doubles are used only by
offline tests and never as evaluation evidence. The harness records actual model
outputs and provenance under `evidence/evaluations/`; it does not manufacture
variation or lower any approved threshold.

See [the quickstart](specs/001-natural-language-reminder-agent/quickstart.md)
and [evaluation strategy](specs/001-natural-language-reminder-agent/evaluation-strategy.md)
for local-runtime verification, scoring gates, and evidence requirements.
