# Test Strategy

The acceptance tests below are mandatory tests represented in Part-1A `tests/`
and executed only through the canonical trusted runner. Submitted repository
copies of tests, `.harness/` scripts and controls, and evidence are untrusted
candidates/evidence; repository location alone does not establish trust. The
authoritative runner, canonical test/control baseline, approval records, and
execution environment are separately protected. Before each run the canonical
runner verifies exact SHA-256 digests against the protected baseline, stages
only verified immutable bytes, and fails closed with a non-zero exit if
verification fails. The trusted store must be protected by a different Windows
identity/ACL or protected CI permissions. If that boundary cannot be
demonstrated, D-01 remains blocked and no authoritative run is permitted.

Use pytest and an in-process ASGI client for API contract tests so application
tests do not contact external network services. Unit tests cover business rules;
repository tests use isolated temporary directories and controlled filesystem
failures. Concurrency tests exercise requests within one process and assert
serializable outcomes without asserting which concurrent request receives a
particular ID.

### Validation Candidate Manifest

Before each authoritative run, the canonical runner calculates a sorted
per-file SHA-256 validation candidate manifest over all application source,
tests, harness scripts/configuration, dependency files, required project/test
files, approved Spec Kit artifacts, `.harness/instruction-files.json`, and only
the exact instruction/governing files listed in that inventory. The inventory
uses the keys `path`, `purpose`, `classification`, `sha256`, and
`approval_reference`, with exact values; it has no wildcard entries. The
canonical runner verifies the inventory and listed-file digests against the
protected baseline. It
includes at least `src/`, `.gitignore`, `pyproject.toml`, `uv.lock`, mandatory
`tests/`, `.harness/`, and `specs/001-smart-todo-api/`. It excludes generated
evidence, runtime data, virtual environments, caches, and enumerated ephemeral
files. The manifest is stored in the protected trust store and identifies the
immutable, run-specific snapshot used for validation. The test process runs
from the staged root and imports the staged `src/` package, never the mutable
workspace. The publication candidate must match this tested candidate manifest
before publication.

### Evidence Bundle Manifest

Runner results/logs, initial/final snapshot references, failure evidence, repair
history, and human security-review/decision records are captured separately in
an evidence bundle. Its own sorted SHA-256 evidence bundle manifest covers all
bundle files and records the exact candidate-manifest digest for each run;
final human review/decision records bind to the final validated candidate.
Verify bundle integrity before publication. Adding or updating evidence does
not change a validation candidate digest; evidence changes instead require a
valid updated evidence manifest and protection of the authoritative bundle.
Store the evidence manifest as a detached protected record, not as a member of
the file set it hashes.

| Acceptance criterion | Planned test focus |
|---|---|
| AC-001 | API: create a valid task; verify `201`, full representation, `Location`, and defaults. |
| AC-002 | Service/API: repeat sequential creation from equal initial states; verify deterministic IDs and no reuse after delete/restart. |
| AC-003 | API: retrieve existing/missing tasks and list empty/non-empty collections with correct count. |
| AC-004 | API/service: partial updates change supplied fields, preserve omitted fields, and reject empty updates. |
| AC-005 | API: delete returns `204` without a body; subsequent reads/deletes return `404`. |
| AC-006 | Domain/API: trim, lowercase, deduplicate, and sort tags on create and update. |
| AC-007 | API/domain: single-tag, AND multi-tag, duplicate-filter normalization, and successful zero-match response. |
| AC-008 | API/domain: all priority values, default `Medium`, and invalid-value rejection. |
| AC-009 | Domain/API: priority ordering, ID tie-break, and default ID ordering. |
| AC-010 | Domain/API: new task defaults to `Pending`; all allowed enum values serialize. |
| AC-011 | Service/API: both allowed transitions persist; same-status transition is an idempotent no-op. |
| AC-012 | Service/API: all prohibited transitions return `409` and preserve task state. |
| AC-013 | Persistence/API: restart against the same file and verify task data and next ID. |
| AC-014 | Persistence/API: successful complete replacement; inject write and replace failures; assert `500`, byte-identical old file, unchanged in-memory reads, and unchanged next ID. |
| AC-015 | Persistence/API: start successfully with each malformed fixture; on every store access assert `500 malformed_stored_data`, no stack trace, and byte-identical source file. |
| AC-016 | API/domain: title and description types, null handling, trimming, and exact lower/upper boundaries. |
| AC-017 | API/domain: tag list count, type, normalized length, empty values, and case-variant deduplication. |
| AC-018 | API: malformed JSON, invalid IDs, query values, enum values, unknown fields, and non-object bodies return the specified codes/statuses. |
| AC-019 | API contract: exercise every endpoint's success shape and applicable error statuses, including malformed JSON on both PATCH routes. |
| AC-020 | API: assert the exact error envelope; every field detail has exactly string fields `field`, `code`, and `message`; no-field errors use `[]`; detail ordering is by field path, then code/message ties; no stack traces, paths, or internal details. |
| AC-021 | Determinism: run the same sequential request sequence from identical initial stores and compare status, data, and ordering. |
| AC-022 | Runner: verify zero Ruff violations, all mandatory tests pass, criterion mapping, Bandit exit code/stdout/stderr/machine-readable findings and execution status, network isolation, staged-package imports, candidate-manifest binding, separate evidence-bundle integrity/reference, and publication-candidate equality; confirm the runner does not create human dispositions or ACCEPT/REJECT. |
| AC-023 | Harness integrity: use disposable trust-store/baseline fixtures to verify submitted repository copies are untrusted and the first invocation uses the canonical runner. Test exact hashes for runner, mandatory tests, expected results, controls, `.harness/instruction-files.json`, and each inventoried file; reject wildcard/unlisted entries and unauthorized modifications before application tests. Verify only the matching immutable snapshot executes, failure evidence is runner-generated, and the runner exits non-zero. Never modify the real canonical baseline. |
| AC-024 | Harness approval: using disposable protected-store fixtures, reject unapproved changes to mandatory tests, expected results, controls, instruction inventory, or inventoried instruction files; reject missing, tampered, or mismatched approval records; accept only exact new digests with approver, date, rationale, old/new hashes, and protected baseline update. Never edit real approval records or baselines. |
| AC-025 | Architecture/runtime: verify Python 3.12/FastAPI/Pydantic, route/service/persistence boundaries, an abstract repository port, no domain dependency on concrete JSON persistence or persistence errors, and API-boundary translation of persistence exceptions. |
| AC-026 | Repository hygiene: prove detection with synthetic secret/environment/private-key fixtures outside the publication set; verify zero findings in the actual publication set. |
| AC-027 | Human security gate: block publication unless a human reviews each Bandit finding and records resolution or documented disposition, rationale, reviewer identity/date, scope, and whether the review gate is satisfied. Verify Bandit execution alone cannot create or impersonate this decision. |
| AC-028 | Human decision gate: verify the runner cannot set a decision, missing decision blocks publication, `REJECT` blocks, and only a recorded human `ACCEPT` opens the gate. |
| AC-029 | Concurrency: issue concurrent mutations in one process; verify serializable responses/final state, no lost mutations, unique sequential IDs, persisted `next_id` and next ID after restart, no request-to-ID ordering assumption, and no in-memory commit after a failed persistence operation. |

### Supplemental Harness Test (not a new acceptance criterion)

| Test ID | Planned test focus |
|---|---|
| HT-001 | Staging isolation: use a disposable repository and trust-store fixture; stage the candidate, then change or remove source, tests, and project files in the original working directory. Verify that execution and imports still use only staged bytes, the validation candidate manifest remains unchanged, and the result records its digest. Change a publication-candidate file after testing and verify publication is rejected and a complete validation rerun is required. Never alter the real canonical baseline. |
| HT-002 | Manifest separation: use disposable candidate and evidence fixtures. Verify the pre-run validation candidate digest excludes generated evidence/runtime/cache files; results and human records in the separate evidence bundle reference the exact candidate digest; changing or corrupting evidence is detected by evidence-manifest verification without changing the candidate digest; the decision references the pre-decision evidence manifest; the final manifest covers the decision without self-reference; and publication fails if the candidate differs or the evidence bundle is not intact. Never alter the real canonical baseline or approval records. |

The independent canonical runner must verify its protected SHA-256 baseline and
approval register before any repository runner, mandatory test, or application
check executes. The first authoritative execution starts from the canonical
runner in the protected trust store, not an unverified repository copy. The
initial run record and every later result bind to that run's validation
candidate digest; the separately manifested evidence bundle records all run
digests and verifies its integrity without changing any candidate digest.
Human review and decision records are added after final automated validation
and remain human actions. Direct local pytest runs may assist development but
do not constitute the authoritative acceptance result.
