from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from reminder_agent.config import ConfigurationError, Settings
from reminder_agent.errors import AgentError, InvalidModelOutputError
from reminder_agent.evaluation import (
    aggregate_scores,
    check_equivalence_groups,
    evaluate_case_run,
    incomplete_reason,
    validate_dataset,
)
from reminder_agent.ollama_client import OllamaClient
from reminder_agent.prompts import build_messages, load_prompt_bundle
from reminder_agent.schemas import InterpretationRequest
from reminder_agent.service import InterpretationService


ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = ROOT / "evals" / "dataset.json"
SERVER_EVIDENCE_PATH = (
    ROOT / "evidence" / "local-runtime" / "ollama-server-process.json"
)
GENERATIONS_PER_CASE = 3


def main() -> int:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    evidence_directory = ROOT / "evidence" / "evaluations" / run_id
    evidence_directory.mkdir(parents=True, exist_ok=False)
    final_snapshot = _capture_final_snapshot(run_id)
    dataset_bytes = DATASET_PATH.read_bytes()
    dataset = json.loads(dataset_bytes)
    validate_dataset(dataset)
    prompt_bundle = load_prompt_bundle()
    dataset_digest = hashlib.sha256(dataset_bytes).hexdigest()

    try:
        settings = Settings.from_env(os.environ)
    except ConfigurationError as exc:
        result = _incomplete_result(
            run_id, "APPLICATION_ERROR", f"Invalid local runtime configuration: {exc}"
        )
        _write_preflight_failure(evidence_directory, result)
        return 2

    cli_observation = _collect_cli_observation()
    server_evidence = _read_server_evidence()
    runtime_info: dict[str, Any] | None = None
    errors: list[dict[str, str]] = []
    try:
        runtime_info = asyncio.run(_preflight(settings))
    except AgentError as exc:
        errors.append({"code": exc.code, "message": exc.public_message})
    except Exception as exc:
        errors.append(
            {
                "code": "APPLICATION_ERROR",
                "message": f"Preflight failed ({type(exc).__name__}).",
            }
        )

    if not cli_observation.get("version"):
        errors.append(
            {
                "code": "OLLAMA_UNAVAILABLE",
                "message": "The Ollama CLI version could not be verified.",
            }
        )
    if not _verify_server_evidence(server_evidence):
        errors.append(
            {
                "code": "OLLAMA_CLOUD_CONFIGURATION_UNVERIFIED",
                "message": "OLLAMA_NO_CLOUD=1 is not verified for the Ollama server process.",
            }
        )
    if settings.endpoint_mode != "loopback":
        errors.append(
            {
                "code": "NON_LOOPBACK_ENDPOINT",
                "message": "Evaluation requires the default local loopback Ollama endpoint.",
            }
        )
    if runtime_info is not None and runtime_info.get("endpoint_mode") != "loopback":
        errors.append(
            {
                "code": "NON_LOOPBACK_ENDPOINT",
                "message": "Ollama preflight used a non-loopback endpoint.",
            }
        )

    if errors:
        reason = _preflight_reason(errors)
        result = _incomplete_result(run_id, reason, "; ".join(item["message"] for item in errors))
        manifest = _build_manifest(
            run_id,
            result,
            dataset,
            dataset_digest,
            prompt_bundle,
            settings,
            cli_observation,
            runtime_info,
            server_evidence,
            _ollama_ps_observation(),
            final_snapshot,
            errors,
            [],
        )
        _write_json(evidence_directory / "manifest.json", manifest)
        _write_json(evidence_directory / "eval-results.json", result)
        _write_json(evidence_directory / "case-runs.json", [])
        failure_directory = ROOT / "evidence" / "failures" / run_id
        failure_directory.mkdir(parents=True, exist_ok=False)
        _write_json(
            failure_directory / "failure-record.json",
            {
                "run_id": run_id,
                "status": "INCOMPLETE",
                "reason": reason,
                "errors": errors,
            },
        )
        print(f"INCOMPLETE: {reason}; no inference calls were made.")
        return 2

    assert runtime_info is not None
    all_case_runs, attempts, completed, successful = asyncio.run(
        _run_generations(dataset, settings, prompt_bundle)
    )
    error_records = [
        {
            "case_id": run["case_id"],
            "run_index": run["run_index"],
            "code": run["error_code"],
            "message": run["error_message"],
        }
        for run in all_case_runs
        if run.get("error_code")
    ]
    error_codes = [item["code"] for item in error_records]
    reason = incomplete_reason(error_codes)
    if completed != 57 and reason is None:
        reason = "INCOMPLETE_GENERATION_COUNT"

    if reason is None and attempts == 57 and completed == 57:
        group_results = check_equivalence_groups(dataset["cases"], all_case_runs)
        for run in all_case_runs:
            for assertion in run["property_assertions"]:
                if assertion["name"] == "equivalence_group_consistent":
                    assertion["passed"] = group_results.get(
                        (run["case_id"], run["run_index"]), False
                    )
        scores = aggregate_scores(all_case_runs)
        result = {
            "run_id": run_id,
            "status": "PASS" if scores["passed"] else "FAIL",
            "reason": None,
            "expected_generation_count": 57,
            "attempted_generation_count": attempts,
            "completed_generation_count": completed,
            "successful_output_count": successful,
            "scores": scores,
            "failed_case_ids": _failed_case_ids(all_case_runs, dataset["cases"]),
            "equivalence_groups": {
                f"{case_id}#{index}": passed
                for (case_id, index), passed in group_results.items()
            },
        }
    else:
        result = {
            "run_id": run_id,
            "status": "INCOMPLETE",
            "reason": reason or "BLOCKED_INFRASTRUCTURE",
            "expected_generation_count": 57,
            "attempted_generation_count": attempts,
            "completed_generation_count": completed,
            "successful_output_count": successful,
            "scores": None,
            "failed_case_ids": [],
        }
    result["observed_output_variation"] = _output_variation(all_case_runs)

    manifest = _build_manifest(
        run_id,
        result,
        dataset,
        dataset_digest,
        prompt_bundle,
        settings,
        cli_observation,
        runtime_info,
        server_evidence,
        _ollama_ps_observation(),
        final_snapshot,
        error_records,
        all_case_runs,
    )
    _write_json(evidence_directory / "manifest.json", manifest)
    _write_json(evidence_directory / "eval-results.json", result)
    _write_json(evidence_directory / "case-runs.json", all_case_runs)
    if result["status"] != "PASS":
        failure_directory = ROOT / "evidence" / "failures" / run_id
        failure_directory.mkdir(parents=True, exist_ok=False)
        _write_json(failure_directory / "failure-record.json", {
            "run_id": run_id,
            "status": result["status"],
            "reason": result.get("reason"),
            "failed_case_ids": result.get("failed_case_ids", []),
            "errors": error_records,
            "case_runs": [
                run
                for run in all_case_runs
                if not run["structural_pass"]
                or any(not item["passed"] for item in run["critical_assertions"])
                or any(not item["passed"] for item in run["property_assertions"])
                or run["semantic"]["score"] < 100
            ],
        })
    print(
        f"{result['status']}: {completed}/57 completed actual generations; "
        f"{successful} raw model outputs; evidence: {evidence_directory}"
    )
    return 0 if result["status"] == "PASS" else (1 if result["status"] == "FAIL" else 2)


async def _run_generations(
    dataset: dict[str, Any], settings: Settings, prompt_bundle: Any
) -> tuple[list[dict[str, Any]], int, int, int]:
    client = OllamaClient(settings)
    service = InterpretationService(client, settings)
    case_runs: list[dict[str, Any]] = []
    attempted = 0
    completed = 0
    successful = 0
    try:
        for case in dataset["cases"]:
            request = InterpretationRequest(
                text=case["text"],
                reference_datetime=case["reference_datetime"],
                timezone=case["timezone"],
            )
            messages = build_messages(
                prompt_bundle,
                request.text,
                request.reference_datetime.isoformat(),
                request.timezone,
            )
            for run_index in range(1, GENERATIONS_PER_CASE + 1):
                attempted += 1
                raw_output: str | None = None
                error_raw_output: str | None = None
                candidate: dict[str, Any] | None = None
                output: dict[str, Any] | None = None
                error_code: str | None = None
                error_message: str | None = None
                generation_completed = False
                try:
                    raw_output = await client.generate(
                        messages[0]["content"],
                        messages[1]["content"],
                        prompt_bundle.schema,
                    )
                    successful += 1
                    completed += 1
                    generation_completed = True
                    try:
                        parsed_candidate = json.loads(raw_output)
                        candidate = (
                            parsed_candidate if isinstance(parsed_candidate, dict) else None
                        )
                    except (TypeError, json.JSONDecodeError):
                        candidate = None
                    try:
                        result = service.interpret_response(request, raw_output)
                        output = result.model_dump(mode="json")
                    except InvalidModelOutputError as exc:
                        error_code = exc.code
                        error_message = exc.public_message
                        error_raw_output = exc.raw_output
                        output = candidate if isinstance(candidate, dict) else None
                except AgentError as exc:
                    error_code = exc.code
                    error_message = exc.public_message
                    if isinstance(exc, InvalidModelOutputError):
                        completed += 1
                        generation_completed = True
                        error_raw_output = exc.raw_output
                        try:
                            candidate = json.loads(exc.raw_output or "")
                            candidate = candidate if isinstance(candidate, dict) else None
                            output = candidate
                        except (TypeError, json.JSONDecodeError):
                            output = None
                except Exception as exc:
                    error_code = "APPLICATION_ERROR"
                    error_message = f"Evaluation failed ({type(exc).__name__})."

                if error_code == "INVALID_MODEL_OUTPUT":
                    evaluation = evaluate_case_run(
                        case,
                        output,
                        prompt_bundle.schema,
                        model_candidate=candidate,
                        error_code=error_code,
                    )
                elif error_code in {
                    "OLLAMA_UNAVAILABLE",
                    "MODEL_NOT_INSTALLED",
                    "INFERENCE_TIMEOUT",
                    "APPLICATION_ERROR",
                }:
                    evaluation = {
                        "case_id": case["case_id"],
                        "structural_pass": False,
                        "structural_errors": [error_code],
                        "property_assertions": [
                            {"name": name, "passed": False}
                            for name in case["property_assertions"]
                        ],
                        "critical_assertions": [
                            {"name": name, "passed": False}
                            for name in case["critical_invariants"]
                        ],
                        "semantic": {
                            "score": 0.0,
                            "intent_points": 0,
                            "required_value_points": 0,
                            "quality_points": 0,
                        },
                        "output": None,
                        "generated_output": candidate,
                    }
                else:
                    evaluation = evaluate_case_run(
                        case,
                        output,
                        prompt_bundle.schema,
                        model_candidate=candidate,
                    )

                case_runs.append(
                    {
                        **evaluation,
                        "run_index": run_index,
                        "reference_datetime": case["reference_datetime"],
                        "timezone": case["timezone"],
                        "text": case["text"],
                        "fr_ids": case["fr_ids"],
                        "ac_ids": case["ac_ids"],
                        "generation_completed": generation_completed,
                        "generation_status": (
                            "completed" if generation_completed else "failed"
                        ),
                        "raw_model_output": raw_output
                        if raw_output is not None
                        else error_raw_output,
                        "generated_output": candidate,
                        "error_code": error_code,
                        "error_message": error_message,
                    }
                )
    finally:
        await client.aclose()
    return case_runs, attempted, completed, successful


async def _preflight(settings: Settings) -> dict[str, Any]:
    client = OllamaClient(settings)
    try:
        return await client.preflight()
    finally:
        await client.aclose()


def _output_variation(case_runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for run in case_runs:
        grouped.setdefault(run["case_id"], []).append(run)
    variation = []
    for case_id, runs in grouped.items():
        outputs = {
            run["run_index"]: run["raw_model_output"]
            for run in runs
            if run.get("raw_model_output") is not None
        }
        distinct_outputs = set(outputs.values())
        variation.append(
            {
                "case_id": case_id,
                "completed_raw_output_count": len(outputs),
                "distinct_output_count": len(distinct_outputs),
                "differing_run_indexes": (
                    sorted(outputs) if len(distinct_outputs) > 1 else []
                ),
            }
        )
    return variation


def _build_manifest(
    run_id: str,
    result: dict[str, Any],
    dataset: dict[str, Any],
    dataset_digest: str,
    prompt_bundle: Any,
    settings: Settings,
    cli_observation: dict[str, Any],
    runtime_info: dict[str, Any] | None,
    server_evidence: dict[str, Any] | None,
    ps_observation: dict[str, Any],
    final_snapshot: str,
    errors: list[dict[str, Any]],
    case_runs: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "execution_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": result["status"],
        "reason": result.get("reason"),
        "dataset_version": dataset["dataset_version"],
        "dataset_path": "evals/dataset.json",
        "dataset_sha256": dataset_digest,
        "case_count": len(dataset["cases"]),
        "expected_generation_count": 57,
        "attempted_generation_count": result.get("attempted_generation_count", 0),
        "completed_generation_count": result.get("completed_generation_count", 0),
        "successful_output_count": result.get("successful_output_count", 0),
        "ollama_cli": cli_observation,
        "ollama_runtime": runtime_info,
        "ollama_server_process_evidence": _safe_server_evidence(server_evidence),
        "endpoint": {
            "base_url": settings.ollama_base_url,
            "mode": settings.endpoint_mode,
        },
        "selected_model": settings.ollama_model,
        "installed_model": runtime_info.get("model") if runtime_info else None,
        "local_model_inventory": runtime_info.get("inventory") if runtime_info else None,
        "ollama_ps": ps_observation,
        "prompt_version": prompt_bundle.version,
        "prompt_sha256": prompt_bundle.sha256,
        "generation_parameters": {
            "temperature": settings.model_temperature,
            "top_p": settings.model_top_p,
            "top_p_applied": True,
            "context_length": settings.model_context_length,
            "timeout_seconds": settings.ollama_timeout,
            "options_sent": {
                "temperature": settings.model_temperature,
                "top_p": settings.model_top_p,
                "num_ctx": settings.model_context_length,
            },
            "tools_enabled": False,
        },
        "per_case_temporal_context": [
            {
                "case_id": case["case_id"],
                "reference_datetime": case["reference_datetime"],
                "timezone": case["timezone"],
            }
            for case in dataset["cases"]
        ],
        "scores": result.get("scores"),
        "observed_output_variation": _output_variation(case_runs),
        "failed_case_ids": result.get("failed_case_ids", []),
        "errors": errors,
        "final_source_snapshot": final_snapshot,
        "case_runs_path": "case-runs.json",
        "evaluation_results_path": "eval-results.json",
    }


def _collect_cli_observation() -> dict[str, Any]:
    executable = shutil.which("ollama")
    if not executable:
        return {"available": False, "version": None, "error": "ollama CLI not found"}
    try:
        completed = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        version = (completed.stdout or completed.stderr).strip()
        return {
            "available": completed.returncode == 0,
            "executable": executable,
            "version": version if completed.returncode == 0 else None,
            "return_code": completed.returncode,
            "error": None if completed.returncode == 0 else "version command failed",
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "available": False,
            "version": None,
            "error": type(exc).__name__,
        }


def _ollama_ps_observation() -> dict[str, Any]:
    executable = shutil.which("ollama")
    if not executable:
        return {"available": False, "output": None, "error": "ollama CLI not found"}
    try:
        completed = subprocess.run(
            [executable, "ps"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        output = (completed.stdout or "").strip()
        return {
            "available": completed.returncode == 0,
            "return_code": completed.returncode,
            "output": output,
            "error": None
            if completed.returncode == 0
            else (completed.stderr or "ollama ps failed").strip(),
            "offload_observation": _infer_offload(output),
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "available": False,
            "output": None,
            "error": type(exc).__name__,
            "offload_observation": "unavailable",
        }


def _infer_offload(output: str) -> str:
    if not output:
        return "unavailable"
    lowered = output.lower()
    if "100% gpu" in lowered or "gpu" in lowered and "cpu" not in lowered:
        return "GPU-resident"
    if "100% cpu" in lowered or "cpu" in lowered and "gpu" not in lowered:
        return "CPU-resident"
    if "gpu" in lowered and "cpu" in lowered:
        return "partially offloaded"
    return "unavailable"


def _read_server_evidence() -> dict[str, Any] | None:
    if not SERVER_EVIDENCE_PATH.is_file():
        return None
    try:
        value = json.loads(SERVER_EVIDENCE_PATH.read_text(encoding="utf-8-sig"))
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _verify_server_evidence(evidence: dict[str, Any] | None) -> bool:
    if not evidence:
        return False
    required = (
        evidence.get("verified") is True
        and evidence.get("ollama_no_cloud") == "1"
        and evidence.get("ollama_host") == "127.0.0.1:11434"
        and evidence.get("server_started_after_setting") is True
        and isinstance(evidence.get("process_name"), str)
        and evidence["process_name"].lower() == "ollama.exe"
        and isinstance(evidence.get("process_id"), int)
        and bool(evidence.get("verification_method"))
    )
    if not required or os.name != "nt":
        return False
    try:
        process_list = subprocess.run(
            [
                "tasklist",
                "/FI",
                f"PID eq {evidence['process_id']}",
                "/FO",
                "CSV",
                "/NH",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return process_list.returncode == 0 and "ollama.exe" in process_list.stdout.lower()


def _safe_server_evidence(evidence: dict[str, Any] | None) -> dict[str, Any] | None:
    if evidence is None:
        return None
    keys = (
        "verified",
        "verification_method",
        "ollama_no_cloud",
        "ollama_host",
        "server_started_after_setting",
        "process_id",
        "process_name",
        "launched_at_utc",
        "ollama_version",
    )
    return {key: evidence.get(key) for key in keys}


def _preflight_reason(errors: list[dict[str, str]]) -> str:
    codes = [item["code"] for item in errors]
    return incomplete_reason(codes) or "BLOCKED_INFRASTRUCTURE"


def _incomplete_result(run_id: str, reason: str, message: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "status": "INCOMPLETE",
        "reason": reason,
        "message": message,
        "expected_generation_count": 57,
        "attempted_generation_count": 0,
        "completed_generation_count": 0,
        "successful_output_count": 0,
        "scores": None,
        "failed_case_ids": [],
    }


def _write_preflight_failure(
    evidence_directory: Path, result: dict[str, Any]
) -> None:
    _write_json(evidence_directory / "manifest.json", result)
    _write_json(evidence_directory / "eval-results.json", result)
    _write_json(evidence_directory / "case-runs.json", [])


def _failed_case_ids(
    case_runs: list[dict[str, Any]], cases: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    case_map = {case["case_id"]: case for case in cases}
    failed = []
    for run in case_runs:
        if (
            not run["structural_pass"]
            or any(not item["passed"] for item in run["critical_assertions"])
            or any(not item["passed"] for item in run["property_assertions"])
            or run["semantic"]["score"] < 85
        ):
            case = case_map[run["case_id"]]
            failed.append(
                {
                    "case_id": run["case_id"],
                    "run_index": run["run_index"],
                    "fr_ids": case["fr_ids"],
                    "ac_ids": case["ac_ids"],
                }
            )
    return failed


def _capture_final_snapshot(run_id: str) -> str:
    destination = ROOT / "evidence" / "final-generation" / run_id
    destination.mkdir(parents=True, exist_ok=False)
    for name in (
        "src",
        "tests",
        "prompts",
        "specs",
        "evals",
        ".harness",
        ".specify",
        "scripts",
    ):
        path = ROOT / name
        if path.exists():
            shutil.copytree(path, destination / name)
    for name in (
        "pyproject.toml",
        "uv.lock",
        "README.md",
        ".env.example",
        ".gitignore",
    ):
        path = ROOT / name
        if path.is_file():
            shutil.copy2(path, destination / name)
    return str(destination.relative_to(ROOT)).replace("\\", "/")


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=_json_default) + "\n",
        encoding="utf-8",
    )


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Cannot serialize {type(value).__name__}.")


if __name__ == "__main__":
    sys.exit(main())
