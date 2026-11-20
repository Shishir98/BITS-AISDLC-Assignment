# Validation Quickstart

This guide describes the implemented service and evaluation workflow.

## Prerequisites

- Python 3.12
- uv
- Ollama installed and running locally
- The configured local model; default `qwen3.5:9b`. Do not select an Ollama
  cloud model or silently substitute another model.

Verify installation with `ollama list` and the server's `/api/tags` inventory.
If `qwen3.5:9b` is not installed, the explicit installation command is
`ollama pull qwen3.5:9b`. Evaluation must remain incomplete until the exact
configured model is installed and locally verified.

Configure the Ollama server process with `OLLAMA_NO_CLOUD=1` and restart the
server. This setting belongs to the Ollama server process, not merely the
FastAPI application's environment. On Windows PowerShell, set and verify the
value in the shell that will launch the server:

```powershell
$env:OLLAMA_NO_CLOUD = '1'
if ($env:OLLAMA_NO_CLOUD -ne '1') { throw 'OLLAMA_NO_CLOUD is not enabled for this server process.' }
ollama serve
```

Because `ollama serve` is launched from that shell, it inherits the verified
setting. If Ollama runs as a desktop app or service, configure the variable for
that server process, restart it, and inspect the running Ollama process
environment (for example, with Process Explorer) to verify `OLLAMA_NO_CLOUD=1`.
Checking the FastAPI process environment or seeing a localhost base URL does not
verify that cloud features are disabled.

Verify the exact `OLLAMA_MODEL` appears in both `ollama list` and the actual
server's `/api/tags` inventory. Confirm it has no `remote_model` or `remote_host`
metadata; record the selected local inventory entry and the server-process
configuration verification as evaluation evidence.

## Application Configuration

From `Part-1B/` after implementation, configure:

```powershell
$env:OLLAMA_MODEL = '<installed-local-model-id>'
$env:OLLAMA_TIMEOUT = '120'
$env:MODEL_TEMPERATURE = '0.2'
$env:MODEL_TOP_P = '0.9'
$env:MODEL_CONTEXT_LENGTH = '4096'
```

By default, set `OLLAMA_MODEL` to `qwen3.5:9b`; change it only to another
explicitly selected local model. `OLLAMA_BASE_URL` defaults to
`http://127.0.0.1:11434`. All values remain configurable; top-p is sent where
supported. No model API key is required. A non-loopback
`OLLAMA_BASE_URL` must be explicitly set and will be clearly marked as outside the
normal local-only mode.

## Validation Sequence

1. `uv sync --locked` - resolve the checked-in Python environment.
2. `uv run pytest` - run unit, API contract, and HTTP-test-double tests. These
   tests do not create evaluation evidence or a feature PASS.
3. Ensure Ollama is available, verify `OLLAMA_NO_CLOUD=1` in the restarted
   server process, and verify the exact configured local model in the actual
   local inventory.
4. `uv run python .harness/run_evaluation.py` - run the single integrated harness
   against the actual installed Ollama model using `evals/dataset.json`. The
   19-case baseline requires exactly 57 actual generations. This command does
   not use mocked outputs or cloud fallback.
5. The integrated runner records `ollama ps` and GPU/CPU offload when available.
   CPU fallback is an environment/performance observation, not an application
   correctness failure.

The evaluator records evidence under
`evidence/evaluations/<run-id>/`, including Ollama version, verified server-process
configuration, actual local model inventory, model ID/digest/details, prompt and
dataset digests, actual effective generation parameters, fixed case temporal
inputs, all individual generations, and exact-output variation observed across
the repetitions. Outputs are preserved unchanged; variation is never manufactured.
No API key is used.

## Expected Results

- Invalid timezone, missing temporal context, or naive reference datetime is
  rejected as invalid request input.
- Complete supported requests return a valid response matching
  `contracts/interpretation.openapi.yaml`.
- Missing/ambiguous information returns clarification; unsupported requests
  return no actionable fields.
- Ollama unavailable, model missing, timeout, invalid model output, and
  application failures use their distinct error codes.
- Any infrastructure failure or fewer than 57 completed generations for the
  19-case baseline marks the run incomplete and blocks scores/PASS. Invalid
  generated output counts as a structural and semantic evaluation failure.
- Evaluation PASS is permitted only under
  [`evaluation-strategy.md`](evaluation-strategy.md)'s unchanged gates.

  Initial and final source/evaluation snapshots are kept separately in
  `evidence/initial-generation/` and `evidence/final-generation/`; genuine
  failure records are kept in `evidence/failures/`. The student completes the
  narrative harness log and human decision.

## Manual API Smoke Scenario

Send a CREATE request for “Remind me to call Rahul tomorrow at 5 PM” with a fixed
future reference datetime and explicit IANA timezone. Verify `ready/create`,
non-empty `title`, offset-aware future `scheduled_at`, matching `timezone`, null
target/snooze fields, empty clarification questions, and a concise `user_message`.
Repeat with “Remind me tomorrow”; verify clarification and null `scheduled_at`.
