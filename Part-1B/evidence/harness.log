# Part 1B Harness Log

This log records the complete evaluation history. Automated scores and the
student's human review are separate decisions. All scored results below come
from actual local Ollama generations; test doubles were not used for evaluation.

## Selected evaluation

**Run `20261120T130057Z-f197c472`: PASS.** The unchanged dataset and scoring
gates were evaluated after the documented repair iterations. The run completed
all 57 of 57 actual model generations (19 cases, three independent calls each),
recorded 57 raw model outputs, and had no failed case IDs.

| Measure | Observed | Required | Gate |
|---|---:|---:|---|
| Structural | 100.00% | 100% | PASS |
| Critical invariants | 100.00% | 100% | PASS |
| Property/invariant | 100.00% | >=95% | PASS |
| Semantic/quality | 99.47% | >=85% | PASS |
| Aggregate | 99.82% | >=90% | PASS |

The aggregate is calculated as `0.30 * Structural + 0.35 * Property/Invariant
+ 0.35 * Semantic/Quality` using unrounded values. PASS also requires every
critical assertion to pass and all three actual generations per case. The
dataset, fixed inputs, scoring formulas, and thresholds were not changed to
obtain this result.

The [selected machine-readable result](eval-results.json) is an exact copy of
the [run-specific result](evaluations/20261120T130057Z-f197c472/eval-results.json).
See the [manifest](evaluations/20261120T130057Z-f197c472/manifest.json) for
runtime provenance and the [case-runs](evaluations/20261120T130057Z-f197c472/case-runs.json)
for all generated outputs, assertions, scores, and variation records. The
evaluated source snapshot is
[preserved here](final-generation/20261120T130057Z-f197c472/).

## Configuration and provenance

- Application: stateless natural-language reminder interpretation; outputs
  remain proposals and do not execute or persist reminders.
- Runtime: Ollama 0.40.16, local endpoint `http://127.0.0.1:11434`, model
  `qwen3.5:9b`, GGUF `Q4_K_M`, digest
  `56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90`.
- Local-only operation: the controlled launcher set `OLLAMA_NO_CLOUD=1` before
  starting the server; the run manifest records verification and server process
  details. The model was present in the actual local inventory; no cloud
  fallback or model download was used.
- Generation settings: temperature 0.2, top-p 0.9, context length 4096,
  timeout 120 seconds, `think: false`, and no model tools. `ollama ps` observed
  100% GPU for the model. The settings and inventory are recorded in the
  manifest.
- Prompt: version 1.7.0, SHA-256
  `6767752a88d2d7d3274b4cdab3d1a1a19e783d70e4037e98573aeb3fac92fabe`.
  Dataset SHA-256:
  `aaec4699c10bf7dea51ce101a60a604f3f8c6b7a80cfd1cfe95158ee15d50fd3`.
- Dataset: 19 cases (5 representative, 4 boundary, 4 ambiguous/missing,
  2 malformed, and 4 adversarial/guardrail), each evaluated three times with
  its fixed reference datetime and IANA timezone.

## Scoring gates

The pre-established [evaluation strategy](../specs/001-natural-language-reminder-agent/evaluation-strategy.md)
requires structural 100%, critical assertions 100%, property/invariant at least
95%, semantic/quality at least 85%, and aggregate at least 90%. The thresholds,
dataset, and three-run protocol were unchanged throughout iteration.

## Evaluation history

All runs and their raw evidence are retained under `evaluations/`; earlier
failures were not overwritten or removed.

| Run ID | Result | Completed / expected | Structural | Critical | Property | Semantic | Aggregate |
|---|---|---:|---:|---:|---:|---:|---:|
| `20261119T140750Z-9d449348` | INCOMPLETE (preflight) | 0 / 57 | — | — | — | — | — |
| `20261119T142050Z-70312b5d` | FAIL | 57 / 57 | 94.74% | 87.06% | 69.82% | 67.89% | 76.62% |
| `20261119T144532Z-5211a32b` | FAIL | 57 / 57 | 96.49% | 91.04% | 96.49% | 94.91% | 95.94% |
| `20261119T163935Z-91c524e8` | FAIL | 57 / 57 | 50.88% | 45.77% | 43.98% | 41.40% | 45.15% |
| `20261119T171022Z-47414a23` | FAIL | 57 / 57 | 87.72% | 87.06% | 84.21% | 83.51% | 85.02% |
| `20261119T172539Z-824629ec` | FAIL | 57 / 57 | 96.49% | 96.02% | 95.32% | 92.81% | 94.79% |
| `20261120T125133Z-5401508a` | FAIL | 57 / 57 | 100.00% | 99.00% | 92.54% | 86.67% | 92.72% |
| `20261120T125704Z-763a47f1` | FAIL | 57 / 57 | 98.25% | 97.01% | 97.43% | 95.79% | 97.10% |
| `20261120T130057Z-f197c472` | **PASS** | **57 / 57** | **100.00%** | **100.00%** | **100.00%** | **99.47%** | **99.82%** |

The preflight run made no inference calls because the Ollama server's
cloud-disabled configuration could not then be verified. Later runs were
performed after the controlled local-only server launch. The intermediate
scored runs informed implementation and prompt corrections; no run's failures
were reclassified as infrastructure errors to obtain a pass.

## Repair and validation record

Iteration preserved the model, temperature, top-p, context length, timeout,
dataset, and gates. `think: false` was added to the Ollama request, after which
further evidence-supported prompt and deterministic interpretation changes
addressed candidate-level action claims, malformed input, intent recovery, and
time handling. All changes and each re-evaluation are preserved in the run
folders and source snapshots.

Offline verification after the final changes: **98 tests passed** (one
third-party Starlette/AnyIO deprecation warning), and
`uv run --locked --no-sync ruff check src tests .harness` passed. A
repository-wide `ruff check .` also inspects the preserved initial-generation
baseline and reports two unused imports in those archived source files; that
historical snapshot was left unchanged.

After the selected run, the result copy, harness logs, task status, and
traceability status were refreshed. These documentation/evidence-index updates
did not change the evaluated application, prompt, dataset, or scoring rules.

## Human review and residual risks

- **Current human decision: ACCEPT.** After reviewing the selected run, the
  student approved it with the rationale: “I approve this, rsults look good
  overall and all gates are passing well above their set minimum pass lines.”
  The harness does not generate or decide human review.
- The earlier **REJECT** applied to run `20261119T142050Z-70312b5d`, which
  failed its gates; it is not a decision on the selected passing run.
- A PASS on this finite dataset does not prove correctness for all wording,
  timezones, prompt-injection attempts, or model versions. The application
  remains proposal-only and does not schedule or deliver reminders.
