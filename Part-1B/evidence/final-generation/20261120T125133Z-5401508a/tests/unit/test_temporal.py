from datetime import datetime
from zoneinfo import ZoneInfo

from reminder_agent.temporal import (
    analyze_temporal_text,
    has_reminder_description,
    has_supported_reminder_operation,
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


def test_dst_resolution_uses_each_zone_not_a_fixed_transition_date() -> None:
    reference = datetime.fromisoformat("2026-03-01T09:00:00+00:00")
    spring = analyze_temporal_text(
        "Remind me to call on March 29, 2026 at 1:30 AM.", reference, "Europe/London"
    )
    autumn = analyze_temporal_text(
        "Remind me to call on October 25, 2026 at 1:30 AM.", reference, "Europe/London"
    )
    assert spring.issue == "nonexistent"
    assert autumn.issue == "ambiguous"


def test_repeated_time_requires_explicit_occurrence_to_select_fold() -> None:
    reference = datetime.fromisoformat("2026-10-25T09:00:00-04:00")
    first = analyze_temporal_text(
        "Remind me November 1, 2026 at 1:30 AM, first occurrence.",
        reference, "America/New_York",
    )
    second = analyze_temporal_text(
        "Remind me November 1, 2026 at 1:30 AM, second occurrence.",
        reference, "America/New_York",
    )
    assert first.issue is None and first.fold == 0
    assert second.issue is None and second.fold == 1


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


def test_malformed_clock_phrase_is_not_treated_as_a_reminder_description() -> None:
    assert not has_reminder_description(
        "Remind me Tuesday in purple around somethingish o'clock."
    )


def test_only_supported_reminder_operations_are_detected() -> None:
    assert has_supported_reminder_operation(
        "Remind me to call Rahul tomorrow."
    )
    assert has_supported_reminder_operation("Move my dentist reminder.")
    assert has_supported_reminder_operation("Snooze my meeting reminder.")
    assert not has_supported_reminder_operation("blue Tuesday chairing 17 because")
