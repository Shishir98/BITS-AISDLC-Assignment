from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from reminder_agent.schemas import load_response_schema


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
    user_content = json.dumps(
        {
            "text": text,
            "reference_datetime": reference_datetime,
            "timezone": timezone,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return [
        {"role": "system", "content": bundle.content},
        {"role": "user", "content": user_content},
    ]
