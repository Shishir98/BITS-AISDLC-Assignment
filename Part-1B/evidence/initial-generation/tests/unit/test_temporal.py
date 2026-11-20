from datetime import datetime
from zoneinfo import ZoneInfo

from reminder_agent.temporal import (
    analyze_temporal_text,
    validate_scheduled_datetime,
)


def test_relative_tomorrow_uses_supplied_reference_and_timezone() -> None:
    reference = datetime.fromisoformat("2026-03-01T23:30:00-05:00")
    hint = analyze_temporal_text(
        "Remind me to call Rahul tomorrow at 5 PM.",
        reference,
        "America/New_York",
    )
    assert hint.local_datetime.isoformat() == "2026-03-02T17:00:00"


def test_calendar_rollover_resolves_against_fixed_reference() -> None:
    reference = datetime.fromisoformat("2026-12-31T23:30:00-05:00")
    hint = analyze_temporal_text(
        "Remind me to start the year tomorrow at 12:15 AM.",
        reference,
        "America/New_York",
    )
    assert hint.local_datetime.isoformat() == "2027-01-01T00:15:00"


def test_nonexistent_dst_time_is_detected() -> None:
    reference = datetime.fromisoformat("2026-03-01T09:00:00-05:00")
    hint = analyze_temporal_text(
        "Remind me to call the clinic on March 8, 2026 at 2:30 AM.",
        reference,
        "America/New_York",
    )
    assert hint.issue == "nonexistent"


def test_repeated_dst_time_is_detected() -> None:
    reference = datetime.fromisoformat("2026-10-25T09:00:00-04:00")
    hint = analyze_temporal_text(
        "Remind me to call the clinic on November 1, 2026 at 1:30 AM.",
        reference,
        "America/New_York",
    )
    assert hint.issue == "ambiguous"


def test_schedule_must_use_valid_zone_offset_and_be_strictly_future() -> None:
    reference = datetime.fromisoformat("2026-03-01T09:00:00-05:00")
    good = datetime.fromisoformat("2026-03-02T17:00:00-05:00")
    assert validate_scheduled_datetime(good, reference, "America/New_York")
    assert not validate_scheduled_datetime(reference, reference, "America/New_York")
    wrong_offset = datetime.fromisoformat("2026-03-02T17:00:00+00:00")
    assert not validate_scheduled_datetime(
        wrong_offset, reference, "America/New_York"
    )
    assert ZoneInfo("America/New_York").key == "America/New_York"
