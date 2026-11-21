# PART 1C — ASSESSED REFLECTION QUESTIONS

## 1. Specification influence

For Part 1A, the human-approved D-05 amendment in constitution v2.0.0 and feature specification v1.4.0 replaced unsupported Windows atomic-visibility claims with an application-level backup, byte-verification, restoration, and fail-closed persistence contract. The implementation preserves exact prior bytes and remains fail-closed in `src/smart_todo/persistence/json_repository.py`; AT-014 verifies those application-handled failure cases. This decision traces directly from the approved amendment to FR-014, AC-014, and the persistence implementation/tests.

## 2. Harness value in Part 1A

The deterministic harness detected AT-008's explicit `priority: null` failure: the initial implementation accepted the null value and returned HTTP 201 instead of rejecting it with HTTP 422. The `pytest-and-traceability` gate supplied the JUnit failure and the harness log preserved the expected-versus-observed behaviour. The repair tightened request validation and the targeted AT-008/AT-029 revalidation passed. Independent Ruff, pytest, and Bandit execution also provided stronger evidence than agent self-review.

## 3. Evaluating non-determinism in Part 1B

REP-001 and REP-002 are suitable cases where exact string matching is inappropriate because equivalent wording can produce different but valid generated JSON text. The harness instead validates the fixed JSON schema and enums, checks the CREATE status/intent, title and timezone-aware future datetime, and evaluates semantic equivalence with the ground truth and equivalence-group properties. This distinguishes structural correctness, temporal correctness, and semantic fidelity without requiring identical prose.

## 4. Feedback and self-healing

In the Part 1B repair history, the 2026-11-19 runs failed because model outputs produced missing/invalid structured values and, in some cases, reached the context limit. The harness supplied actual model outputs, invalid-structure information, failed critical/property assertions, and run manifests back to the repair process. The prompt, deterministic temporal context, strict output validation, and guardrails were corrected while preserving the same dataset, three-run protocol, scoring formula, and thresholds. The repair produced PASS in run `20261120T130057Z-f197c472` with 57/57 complete actual generations.

## 5. Human accountability

For Part 1B, the passing finite dataset does not prove correctness for every wording, timezone, prompt-injection strategy, or future model version. I reviewed the selected run and recorded ACCEPT. Before a higher-risk production deployment, I would add a larger continuously updated evaluation set, repeated cross-model evaluation, production monitoring, stricter prompt-injection red teaming, explicit privacy/security review, and a review-and-rollback process for model or prompt changes.
