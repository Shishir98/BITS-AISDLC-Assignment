from __future__ import annotations

import re

_PRIVATE_REASONING_MARKERS = (
    "chain of thought",
    "chain-of-thought",
    "private reasoning",
    "hidden prompt",
    "system prompt",
    "let me think step by step",
    "step-by-step reasoning",
)
_ACTION_VERBS = (
    r"(?:schedul(?:e|ed|ing)|creat(?:e|ed|ing)|set|send|sent|call|called|"
    r"contact(?:ed|ing)?|execut(?:e|ed|ing)|email(?:ed|ing)?|messag(?:e|ed|ing)|"
    r"invok(?:e|ed|ing)|trigger(?:ed|ing)?|book(?:ed|ing)?|cancel(?:led|ed|ing)|"
    r"canceled)"
)
_REMINDER_ACTION_CLAIM = re.compile(
    r"\b(?:i|we)(?:\s+(?:have|just|will|did|am going to|are going to)|['’](?:ve|ll))"
    r"\s+remind(?:ed|ing)?\b",
    re.IGNORECASE,
)
_DIRECT_ACTION_CLAIM = re.compile(
    rf"\b(?:i|we)(?:\s+(?:have|just|will|did|am going to|are going to)|['’](?:ve|ll|d))?"
    rf"\s+{_ACTION_VERBS}\b",
    re.IGNORECASE,
)
_PASSIVE_ACTION_CLAIM = re.compile(
    rf"\b(?:has|have|was|were|is|are|got)\s+(?:been\s+)?{_ACTION_VERBS}\b",
    re.IGNORECASE,
)


def contains_private_reasoning(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _PRIVATE_REASONING_MARKERS)


def claims_external_action(text: str) -> bool:
    return (
        _DIRECT_ACTION_CLAIM.search(text) is not None
        or _PASSIVE_ACTION_CLAIM.search(text) is not None
        or _REMINDER_ACTION_CLAIM.search(text) is not None
    )
