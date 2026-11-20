from reminder_agent.prompts import build_messages, load_prompt_bundle
import json


def test_system_prompt_contains_contract_and_explicit_temporal_context() -> None:
    bundle = load_prompt_bundle()
    messages = build_messages(
        bundle,
        "Remind me tomorrow at 5 PM.",
        "2026-03-01T09:00:00-05:00",
        "America/New_York",
    )
    assert "CREATE" in messages[0]["content"]
    assert "untrusted" in messages[0]["content"].lower()
    assert "reference_datetime" in messages[1]["content"]
    assert "2026-03-01T09:00:00-05:00" in messages[1]["content"]
    assert "America/New_York" in messages[1]["content"]
    assert bundle.sha256


def test_prompt_context_exposes_dst_issue_without_choosing_an_instant() -> None:
    messages = build_messages(
        load_prompt_bundle(),
        "Remind me to call the clinic on March 8, 2026 at 2:30 AM.",
        "2026-03-01T09:00:00-05:00",
        "America/New_York",
    )
    context = json.loads(messages[1]["content"])["temporal_analysis"]
    assert context["issue"] == "nonexistent"
    assert context["resolved_datetime"] is None


def test_prompt_context_resolves_weekday_from_explicit_reference() -> None:
    messages = build_messages(
        load_prompt_bundle(),
        "Move my dentist reminder to Friday at 6 PM.",
        "2026-03-01T09:00:00-05:00",
        "America/New_York",
    )
    context = json.loads(messages[1]["content"])["temporal_analysis"]
    assert context["resolved_datetime"] == "2026-03-06T18:00:00-05:00"
