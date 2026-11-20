from reminder_agent.prompts import build_messages, load_prompt_bundle


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
