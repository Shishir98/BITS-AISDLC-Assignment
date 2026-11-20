# Test Strategy

The acceptance tests below are mandatory tests represented in Part-1A `tests/`
and intended to run through the selected GitHub Actions workflow dispatched
from protected `main`. Submitted repository copies of tests, `.harness/` scripts
and controls, and evidence remain untrusted candidates/evidence; repository
location alone does not establish trust. The workflow must verify exact
SHA-256 digests against a human-approved baseline, stage only verified
run-specific bytes, verify integrity before and after execution, and fail
closed with a non-zero exit if verification fails. The workflow uses a
read-only token and provides no secrets to candidate code. A protected branch
ruleset alone does not establish canonical runner independence; D-01 remains
blocked until the workflow, approved baseline, execution boundary, and actual
protected run are verified. No additional Windows account is required.

Use pytest and an in-process ASGI client for API contract tests so application
tests do not contact external network services. Unit tests cover business rules;
repository tests use isolated temporary directories and controlled filesystem
failures. Concurrency tests exercise requests within one process and assert
serializable outcomes without asserting which concurrent request receives a
particular ID.

During test execution, `tests/conftest.py`, `.harness/test.ps1`, and
`.harness/trust/run_validation.py` enforce process-level network and
test-service isolation: Python TCP (`socket.socket.connect`,
`socket.socket.connect_ex`, `socket.create_connection`), UDP
(`socket.socket.sendto`), DNS (`socket.getaddrinfo`), and HTTP
(`urllib.request.urlopen`) calls to non-loopback hosts are deterministically
blocked while allowing in-process ASGI `TestClient` traffic; subprocess and
package-manager escape paths are restricted via `NO_PROXY=127.0.0.1,localhost,::1`,
`HTTP_PROXY=http://127.0.0.1:9`, `HTTPS_PROXY=http://127.0.0.1:9`,
`ALL_PROXY=http://127.0.0.1:9`, `PIP_NO_INDEX=1`, `UV_OFFLINE=1`,
`PYTHONNOUSERSITE=1`, and `UV_NO_CONFIG=1` (with `uv run --locked --no-sync`
after dependency sync). **Hosted-runner OS limitation**: standard GitHub-hosted
`windows-latest` runners do not provide an unprivileged hypervisor-level NIC
disconnect during workflow steps, so isolation is enforced at the Python socket,
DNS, HTTP client, package-manager, and environment/proxy layers rather than an
OS kernel firewall.

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
| AC-014 | Persistence/API: verify complete candidate serialization and backup bytes before best-effort replacement; inject candidate/backup write failures, replacement failure before and after primary change, recovery/cleanup failures, and absent-store creation failure. Assert `500 persistence_error`, byte-exact restored bytes or verified absence, unchanged in-memory state, fail-closed behavior with preserved recovery material, and a successful next mutation after verified recovery. These tests cover application-handled failures only and do not establish Windows atomic visibility, crash durability, or abrupt-process/OS recovery. |
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

### Current Repository Test Mapping (Untrusted Diagnostic)

The following exact pytest node IDs are repository candidates, not protected
canonical tests. `PASS` means all active mapped checks passed locally;
`WAIVED` means the independent mapped checks passed and only the stated
custom-bootstrap portion is waived; `NOT VERIFIED` means active protected or
human-only evidence remains unavailable; `FAIL` means a mapped automated check
failed. These labels do not constitute an authoritative acceptance result.

| AC ID | AT ID | Test file | Test name | Local status |
|---|---|---|---|---|
| AC-001 | AT-001 | `tests/api_contract/test_task_crud.py` | `test_at001_create_response_matches_task_contract` | PASS |
| AC-002 | AT-002 | `tests/unit/test_id_allocation.py` | `test_at002_ids_are_deterministic_and_never_reused_after_delete_or_restart` | PASS |
| AC-003 | AT-003 | `tests/api_contract/test_task_crud.py` | `test_at003_list_and_get_reflect_empty_existing_and_missing_tasks` | PASS |
| AC-004 | AT-004 | `tests/api_contract/test_task_crud.py` | `test_at004_patch_changes_only_supplied_fields_and_rejects_empty_update` | PASS |
| AC-005 | AT-005 | `tests/api_contract/test_task_crud.py` | `test_at005_delete_has_no_response_body_and_missing_ids_are_404` | PASS |
| AC-006 | AT-006 | `tests/api_contract/test_task_queries.py` | `test_at006_tags_are_trimmed_lowercased_deduplicated_and_sorted` | PASS |
| AC-007 | AT-007 | `tests/api_contract/test_task_queries.py` | `test_at007_tag_filters_are_anded_normalized_deduplicated_and_can_match_nothing` | PASS |
| AC-008 | AT-008 | `tests/api_contract/test_task_queries.py` | `test_at008_priority_values_default_and_invalid_inputs` | PASS |
| AC-009 | AT-009 | `tests/api_contract/test_task_queries.py` | `test_at009_priority_sort_is_stable_and_uses_task_id_for_ties` | PASS |
| AC-010 | AT-010 | `tests/api_contract/test_status_transitions.py` | `test_at010_all_task_status_values_are_returned` | PASS |
| AC-011 | AT-011 | `tests/api_contract/test_status_transitions.py` | `test_at011_only_forward_transitions_are_allowed_and_same_status_is_idempotent` | PASS |
| AC-012 | AT-012 | `tests/api_contract/test_status_transitions.py` | `test_at012_prohibited_transitions_leave_persisted_status_unchanged` | PASS |
| AC-013 | AT-013 | `tests/persistence/test_json_repository.py` | `test_at013_restart_restores_tasks_and_continues_monotonic_ids` | PASS |
| AC-014 | AT-014 | `tests/persistence/test_json_repository.py` | `test_at014_successful_write_verifies_backup_and_complete_candidate`; `test_at014_candidate_serialization_failure_does_not_touch_store_or_memory`; `test_at014_candidate_temporary_write_failure_recovers_and_allows_next_write`; `test_at014_backup_write_failure_leaves_verified_original_and_memory_unchanged`; `test_at014_replacement_failure_restores_exact_bytes_and_allows_next_write`; `test_at014_replacement_failure_after_install_restores_from_verified_backup`; `test_at014_failed_creation_restores_original_absence`; `test_at014_recovery_failure_preserves_backup_and_fails_closed`; `test_at014_cleanup_failure_does_not_undo_verified_commit` | PASS (local candidate validation; not authoritative) |
| AC-015 | AT-015 | `tests/persistence/test_json_repository.py` | `test_at015_table_driven_malformed_store_fixtures_fail_closed_without_rewriting` | PASS |
| AC-016 | AT-016 | `tests/error_handling/test_request_validation.py` | `test_at016_title_and_description_boundary_values_and_invalid_values` | PASS |
| AC-017 | AT-017 | `tests/error_handling/test_request_validation.py` | `test_at017_tag_count_length_and_normalization_boundaries` | PASS |
| AC-018 | AT-018 | `tests/error_handling/test_request_validation.py` | `test_at018_malformed_json_ids_queries_and_enum_values_are_rejected` | PASS |
| AC-019 | AT-019 | `tests/api_contract/test_endpoint_contract.py` | `test_at019_success_and_applicable_error_statuses_for_every_endpoint` | PASS |
| AC-020 | AT-020 | `tests/error_handling/test_request_validation.py` | `test_at020_validation_errors_have_stable_sanitized_envelope` | PASS |
| AC-021 | AT-021 | `tests/api_contract/test_determinism.py` | `test_at021_identical_initial_state_and_request_sequence_produce_identical_results` | PASS |
| AC-022 | AT-022 | `tests/harness_integrity/test_github_trust_bootstrap.py`; `tests/harness_integrity/test_runner_boundaries.py`; `tests/harness_integrity/test_architecture.py` | `test_at022_workflow_uses_protected_main_read_only_checkout_and_sha`; `test_at022_candidate_process_receives_only_allowlisted_environment`; `test_at022_required_checks_and_in_process_test_client_are_network_independent`; `test_candidate_controls_keep_protected_trust_and_human_records_unavailable` | NOT VERIFIED: automated controls are tested locally, but active protected workflow execution and the independent execution boundary remain unverified. |
| AC-023 | AT-023 | `tests/harness_integrity/test_github_trust_bootstrap.py`; `tests/harness_integrity/test_runner_boundaries.py` | `test_at023_pending_bootstrap_fails_before_candidate_staging`; `test_at023_synthetic_tampered_test_file_is_rejected_before_staging`; `test_at023_unapproved_changes_to_controls_inventory_instructions_and_dependencies_are_rejected`; `test_at023_verified_candidate_is_staged_and_manifest_tampering_is_detected`; `test_at023_untrusted_repository_runner_refuses_authoritative_mode` | WAIVED: mapped candidate and synthetic tamper checks remain active and pass; only the custom-bootstrap portion is waived by the owner. |
| AC-024 | AT-024 | `tests/harness_integrity/test_github_trust_bootstrap.py`; `tests/harness_integrity/test_runner_boundaries.py` | `test_at024_instruction_inventory_paths_and_digests_are_current`; `test_at024_tampered_trusted_workflow_or_approval_register_is_rejected`; `test_at024_instruction_inventory_is_exact_and_current` | WAIVED: inventory and synthetic approval/tamper checks remain active and pass; only the custom-bootstrap approval-register portion is waived by the owner. |
| AC-025 | AT-025 | `tests/harness_integrity/test_architecture.py` | `test_at025_runtime_versions_repository_port_and_layer_boundaries` | PASS |
| AC-026 | AT-026 | `tests/harness_integrity/test_repository_hygiene.py` | `test_at026_synthetic_scanner_fixtures_detect_tracked_secret_like_files`; `test_at026_current_publication_candidate_has_no_hygiene_findings`; `test_at026_historical_synthetic_scanner_fixtures_are_not_publication_findings` | PASS (local candidate scan; not authoritative) |
| AC-027 | AT-027 | `tests/harness_integrity/test_runner_boundaries.py`; `tests/harness_integrity/test_security_review_gate.py` | `test_at027_human_security_review_is_a_separate_unverified_gate`; `test_at027_security_review_verifies_exact_bandit_finding_identities_and_dispositions`; `test_at027_security_review_rejects_count_only_duplicate_fabricated_missing_and_mismatched_findings` | NOT VERIFIED: automated gate behavior is tested; the actual human security review record for T044 remains outstanding. |
| AC-028 | AT-028 | `tests/harness_integrity/test_runner_boundaries.py`; `tests/harness_integrity/test_human_decision.py` | `test_at028_runner_does_not_create_or_infer_acceptance_decisions`; `test_at028_human_decision_gate_reconstructs_pre_decision_digest_and_verifies_acceptance`; `test_at028_human_decision_gate_rejects_pre_decision_tampering_missing_or_unexpected_files_and_reject_decisions` | NOT VERIFIED: automated gate behavior is tested; the actual human final decision for T045 remains outstanding. |
| AC-029 | AT-029 | `tests/concurrency/test_concurrent_mutations.py` | `test_at029_concurrent_creates_have_unique_monotonic_ids_and_survive_restart` | PASS |
