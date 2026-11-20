from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


_WEEKDAYS = {
    name.lower(): index
    for index, name in enumerate(
        ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
    )
}
_MONTHS = {
    name.lower(): index
    for index, name in enumerate(
        (
            "",
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        )
    )
    if name
}
_DATE_PATTERN = re.compile(
    r"\b(?P<month>January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\s+"
    r"(?P<day>\d{1,2})(?:,?\s+(?P<year>\d{4}))?\b",
    re.IGNORECASE,
)
_TIME_PATTERN = re.compile(
    r"\b(?:at\s+)?(?P<hour>1[0-2]|0?[1-9])"
    r"(?::(?P<minute>[0-5]\d))?\s*(?P<period>a\.?m\.?|p\.?m\.?)\b",
    re.IGNORECASE,
)
_TIME_24_PATTERN = re.compile(r"\b(?:at\s+)?(?P<hour>[01]?\d|2[0-3]):(?P<minute>[0-5]\d)\b")
_SNOOZE_DURATION_PATTERN = re.compile(
    r"\b(?:(?:for|by)\s+)?(?:\d+\s*(?:minutes?|mins?|hours?|hrs?)|"
    r"(?:an?|one|two|three|four|five|ten|fifteen|twenty|thirty|sixty)\s+"
    r"(?:minutes?|mins?|hours?|hrs?)|half\s+an?\s+hour)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TemporalHint:
    local_datetime: datetime | None
    date_known: bool
    time_known: bool
    issue: str | None


def analyze_temporal_text(
    text: str, reference_datetime: datetime, timezone_name: str
) -> TemporalHint:
    if reference_datetime.tzinfo is None or reference_datetime.utcoffset() is None:
        raise ValueError("reference_datetime must be timezone-aware")
    zone = ZoneInfo(timezone_name)
    local_reference = reference_datetime.astimezone(zone)
    local_date, date_known, date_issue = _extract_date(text, local_reference)
    local_time, time_known = _extract_time(text)
    if not date_known or not time_known or local_date is None or local_time is None:
        return TemporalHint(None, date_known, time_known, date_issue)

    wall_datetime = datetime.combine(local_date, local_time)
    issue = date_issue or _wall_time_issue(wall_datetime, zone)
    return TemporalHint(wall_datetime, date_known, time_known, issue)


def validate_scheduled_datetime(
    scheduled_at: datetime, reference_datetime: datetime, timezone_name: str
) -> bool:
    if (
        scheduled_at.tzinfo is None
        or scheduled_at.utcoffset() is None
        or reference_datetime.tzinfo is None
        or reference_datetime.utcoffset() is None
    ):
        return False
    zone = ZoneInfo(timezone_name)
    local = scheduled_at.astimezone(zone)
    if local.utcoffset() != scheduled_at.utcoffset():
        return False
    return scheduled_at.astimezone(timezone.utc) > reference_datetime.astimezone(
        timezone.utc
    )


def has_reminder_description(text: str) -> bool:
    remainder = re.sub(r"\bplease\b", " ", text, flags=re.IGNORECASE)
    remainder = re.sub(
        r"\bremind\s+me\b", " ", remainder, flags=re.IGNORECASE
    )
    remainder = re.sub(r"^\s*to\b", " ", remainder, flags=re.IGNORECASE)
    remainder = _remove_temporal_phrases(remainder)
    tokens = re.findall(r"[a-z0-9]+", remainder.lower())
    return any(token not in {"on", "at", "by", "to", "the", "a", "an"} for token in tokens)


def has_explicit_target(text: str) -> bool:
    remainder = re.sub(
        r"\b(?:please|move|reschedule|snooze|my|the|a|an|reminder|"
        r"remind|it|this|that|to|on|by|for)\b",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    remainder = _SNOOZE_DURATION_PATTERN.sub(" ", remainder)
    remainder = _remove_temporal_phrases(remainder)
    return bool(re.findall(r"[a-z0-9]+", remainder.lower()))


def has_snooze_duration(text: str) -> bool:
    return _SNOOZE_DURATION_PATTERN.search(text) is not None


def _extract_date(text: str, reference: datetime) -> tuple[date | None, bool, str | None]:
    lowered = text.lower()
    if re.search(r"\btomorrow\b", lowered):
        return reference.date() + timedelta(days=1), True, None
    if re.search(r"\btoday\b", lowered):
        return reference.date(), True, None

    month_match = _DATE_PATTERN.search(text)
    if month_match:
        year = int(month_match.group("year") or reference.year)
        month = _MONTHS[month_match.group("month").lower()]
        day = int(month_match.group("day"))
        try:
            candidate = date(year, month, day)
        except ValueError:
            return None, True, "invalid_date"
        if month_match.group("year") is None and candidate < reference.date():
            return candidate, True, "past_date_without_year"
        return candidate, True, None

    weekday_match = re.search(
        r"\b(?:(this)\s+|next\s+)?"
        r"(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        lowered,
    )
    if weekday_match:
        target = _WEEKDAYS[weekday_match.group(2)]
        if weekday_match.group(1) == "this":
            current_week_monday = reference.date() - timedelta(
                days=reference.weekday()
            )
            candidate = current_week_monday + timedelta(days=target)
            if candidate < reference.date():
                return candidate, True, "past_weekday"
            return candidate, True, None
        days_ahead = (target - reference.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        return reference.date() + timedelta(days=days_ahead), True, None
    return None, False, None


def _extract_time(text: str) -> tuple[time | None, bool]:
    lowered = text.lower()
    if re.search(r"\bnoon\b", lowered):
        return time(12), True
    if re.search(r"\bmidnight\b", lowered):
        return time(0), True

    match = _TIME_PATTERN.search(text)
    if match:
        hour = int(match.group("hour"))
        minute = int(match.group("minute") or 0)
        period = match.group("period").lower().replace(".", "")
        hour = hour % 12 + (12 if period.startswith("p") else 0)
        return time(hour, minute), True
    match = _TIME_24_PATTERN.search(text)
    if match:
        return time(int(match.group("hour")), int(match.group("minute"))), True
    return None, False


def _remove_temporal_phrases(text: str) -> str:
    remainder = _DATE_PATTERN.sub(" ", text)
    remainder = _TIME_PATTERN.sub(" ", remainder)
    remainder = _TIME_24_PATTERN.sub(" ", remainder)
    remainder = re.sub(
        r"\b(?:today|tomorrow|this|next|monday|tuesday|wednesday|thursday|"
        r"friday|saturday|sunday|noon|midnight)\b",
        " ",
        remainder,
        flags=re.IGNORECASE,
    )
    return remainder


def _wall_time_issue(wall_time: datetime, zone: ZoneInfo) -> str | None:
    valid_offsets: set[timedelta | None] = set()
    for fold in (0, 1):
        candidate = wall_time.replace(tzinfo=zone, fold=fold)
        round_trip = candidate.astimezone(timezone.utc).astimezone(zone)
        if round_trip.replace(tzinfo=None) == wall_time:
            valid_offsets.add(candidate.utcoffset())
    if not valid_offsets:
        return "nonexistent"
    if len(valid_offsets) > 1:
        return "ambiguous"
    return None
