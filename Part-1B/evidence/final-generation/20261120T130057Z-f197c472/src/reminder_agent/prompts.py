from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone as utc_timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from reminder_agent.schemas import load_response_schema
from reminder_agent.temporal import (
    analyze_temporal_text,
    has_explicit_target,
    has_reminder_description,
    has_supported_reminder_operation,
)


@dataclass(frozen=True)
class PromptBundle:
    version: str
    content: str
    sha256: str
    schema: dict


def load_prompt_bundle() -> PromptBundle:
    project_root = Path(__file__).resolve().parents[2]
    prompt_path = project_root / "prompts" / "system_prompt.md"
    content = prompt_path.read_text(encoding="utf-8")
    match = re.search(r"^Prompt version:\s*(\S+)\s*$", content, re.MULTILINE)
    if match is None:
        raise ValueError("The system prompt must declare its version.")
    schema = load_response_schema()
    full_prompt = (
        content.rstrip()
        + "\n\nApproved response JSON Schema:\n"
        + json.dumps(schema, ensure_ascii=False, sort_keys=True)
    )
    digest = hashlib.sha256(full_prompt.encode("utf-8")).hexdigest()
    return PromptBundle(match.group(1), full_prompt, digest, schema)


def build_messages(
    bundle: PromptBundle,
    text: str,
    reference_datetime: str,
    timezone: str,
) -> list[dict[str, str]]:
    reference = datetime.fromisoformat(reference_datetime)
    hint = analyze_temporal_text(text, reference, timezone)
    issue = hint.issue
    resolved = None
    if hint.local_datetime is not None and issue is None:
        candidate = hint.local_datetime.replace(
            tzinfo=ZoneInfo(timezone), fold=hint.fold or 0
        )
        if candidate.astimezone(utc_timezone.utc) <= reference.astimezone(utc_timezone.utc):
            issue = "past_or_equal"
        else:
            resolved = candidate.isoformat()
    user_content = json.dumps(
        {
            "text": text,
            "reference_datetime": reference_datetime,
            "timezone": timezone,
            "input_evidence": {
                "supported_reminder_operation_present": (
                    has_supported_reminder_operation(text)
                ),
                "description_present": has_reminder_description(text),
                "explicit_target_present": has_explicit_target(text),
            },
            "temporal_analysis": {
                "date_known": hint.date_known,
                "time_known": hint.time_known,
                "local_datetime": (
                    hint.local_datetime.isoformat() if hint.local_datetime else None
                ),
                "resolved_datetime": resolved,
                "issue": issue,
            },
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return [
        {"role": "system", "content": bundle.content},
        {"role": "user", "content": user_content},
    ]
