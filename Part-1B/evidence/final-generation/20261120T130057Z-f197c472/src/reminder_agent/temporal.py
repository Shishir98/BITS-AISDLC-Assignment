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
_SNOOZE_NUMBER_PATTERN = re.compile(
    r"\b(?:(?:for|by)\s+)?(?P<amount>\d+)\s*"
    r"(?P<unit>minutes?|mins?|hours?|hrs?)\b",
    re.IGNORECASE,
)
_SNOOZE_WORD_PATTERN = re.compile(
    r"\b(?:(?:for|by)\s+)?(?P<amount>an?|one|two|three|four|five|ten|"
    r"fifteen|twenty|thirty|sixty|half)\s+"
    r"(?P<unit>minutes?|mins?|hours?|hrs?|an?\s+hour)\b",
    re.IGNORECASE,
)
_SUPPORTED_REMINDER_OPERATION_PATTERN = re.compile(
    r"\bremind\s+me\b|\b(?:set|create|add)\s+"
    r"(?:(?:a|an|the|my)\s+)?reminders?\b|\b(?:move|reschedule|snooze)\b",
    re.IGNORECASE,
)
_SNOOZE_OPERATION_PATTERN = re.compile(r"\bsnooze\b", re.IGNORECASE)
_RESCHEDULE_OPERATION_PATTERN = re.compile(r"\b(?:move|reschedule)\b", re.IGNORECASE)


@dataclass(frozen=True)
class TemporalHint:
    local_datetime: datetime | None
    date_known: bool
    time_known: bool
    issue: str | None
    fold: int | None = None


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
    fold = None
    if issue == "ambiguous":
        fold = _explicit_fold(text)
        if fold is not None:
            issue = None
    return TemporalHint(wall_datetime, date_known, time_known, issue, fold)


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


def extract_reminder_description(text: str) -> str | None:
    operation = re.search(r"\bremind\s+me\b", text, re.IGNORECASE)
    if operation is None:
        return None
    description = text[operation.end():]
    description = re.sub(
        r"^\s*(?:to|about)\s+",
        "",
        description,
        flags=re.IGNORECASE,
    )
    description = _remove_temporal_phrases(description)
    description = description.strip(" \t\r\n.,;:!?")
    description = re.sub(r"\b(?:on|at|by)\s*$", "", description, flags=re.IGNORECASE)
    description = re.sub(r"\s+", " ", description).strip(" \t\r\n.,;:!?")
    return description or None


def has_supported_reminder_operation(text: str) -> bool:
    return identify_supported_reminder_intent(text) is not None


def identify_supported_reminder_intent(text: str) -> str | None:
    if _SNOOZE_OPERATION_PATTERN.search(text):
        return "snooze"
    if _RESCHEDULE_OPERATION_PATTERN.search(text):
        return "reschedule"
    if _SUPPORTED_REMINDER_OPERATION_PATTERN.search(text):
        return "create"
    return None


def extract_reminder_target(text: str) -> str | None:
    operation = re.search(r"\b(?:move|reschedule|snooze)\b", text, re.IGNORECASE)
    if operation is None:
        return None
    target = text[operation.end():]
    target = _SNOOZE_DURATION_PATTERN.sub(" ", target)
    target = _remove_temporal_phrases(target)
    target = re.sub(
        r"\b(?:it|this|that|something|anything|to|for|by|on|at|"
        r"later|earlier|now|then)\b",
        " ",
        target,
        flags=re.IGNORECASE,
    )
    target = re.sub(
        r"^\s*(?:my|the|a|an)\s+",
        "",
        target,
        flags=re.IGNORECASE,
    )
    target = re.sub(r"\s+", " ", target).strip(" \t\r\n.,;:!?")
    return target or None


def has_explicit_target(text: str) -> bool:
    remainder = re.sub(
        r"\b(?:please|move|reschedule|snooze|my|the|a|an|reminder|"
        r"remind|it|this|that|to|on|by|for|later|earlier|now|then|"
        r"something|anything)\b",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    remainder = _SNOOZE_DURATION_PATTERN.sub(" ", remainder)
    remainder = _remove_temporal_phrases(remainder)
    return bool(re.findall(r"[a-z0-9]+", remainder.lower()))


def has_snooze_duration(text: str) -> bool:
    return _SNOOZE_DURATION_PATTERN.search(text) is not None


def extract_snooze_minutes(text: str) -> int | None:
    if re.search(r"\bhalf\s+an?\s+hour\b", text, re.IGNORECASE):
        return 30
    numeric = _SNOOZE_NUMBER_PATTERN.search(text)
    if numeric:
        amount = int(numeric.group("amount"))
        unit = numeric.group("unit").lower()
        return amount * 60 if unit.startswith(("hour", "hr")) else amount

    word_match = _SNOOZE_WORD_PATTERN.search(text)
    if not word_match:
        return None
    amount_text = word_match.group("amount").lower()
    amount = {
        "a": 1,
        "an": 1,
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "ten": 10,
        "fifteen": 15,
        "twenty": 20,
        "thirty": 30,
        "sixty": 60,
        "half": 30,
    }[amount_text]
    unit = word_match.group("unit").lower()
    return amount * 60 if "hour" in unit or unit.startswith("hr") else amount


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
    remainder = re.sub(
        r"\b(?:at|around|in)\s+[^.!?]*?\bo['’]?clock\b",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    remainder = _DATE_PATTERN.sub(" ", remainder)
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


def _explicit_fold(text: str) -> int | None:
    occurrences = re.findall(r"\b(first|second)\s+(?:occurrence|instance)\b", text, re.IGNORECASE)
    if len(occurrences) == 1:
        return 0 if occurrences[0].lower() == "first" else 1
    return None
