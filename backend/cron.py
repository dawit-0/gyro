"""Minimal 5-field cron parser. No external dependencies.

Supports: *, */N, N-M, N,M, and literal N for each field.
Fields: minute(0-59) hour(0-23) dom(1-31) month(1-12) dow(0-6, 0=Sun)
"""

from datetime import datetime, timedelta


def _parse_field(field: str, lo: int, hi: int) -> set[int]:
    values: set[int] = set()
    for part in field.split(","):
        if "/" in part:
            base, step = part.split("/", 1)
            step = int(step)
            start = lo if base in ("*", "") else int(base)
            values.update(range(start, hi + 1, step))
        elif part == "*":
            values.update(range(lo, hi + 1))
        elif "-" in part:
            a, b = part.split("-", 1)
            values.update(range(int(a), int(b) + 1))
        else:
            values.add(int(part))
    return values


def parse(expr: str) -> tuple[set[int], set[int], set[int], set[int], set[int]]:
    """Parse a 5-field cron expression into (minutes, hours, doms, months, dows)."""
    fields = expr.strip().split()
    if len(fields) != 5:
        raise ValueError(f"Expected 5 fields, got {len(fields)}: {expr!r}")
    return (
        _parse_field(fields[0], 0, 59),
        _parse_field(fields[1], 0, 23),
        _parse_field(fields[2], 1, 31),
        _parse_field(fields[3], 1, 12),
        _parse_field(fields[4], 0, 6),
    )


def next_run_after(expr: str, after: datetime) -> datetime:
    """Return the next datetime matching the cron expression, strictly after `after`."""
    minutes, hours, doms, months, dows = parse(expr)

    # Start from the next minute
    dt = after.replace(second=0, microsecond=0) + timedelta(minutes=1)

    # Walk forward up to ~4 years to find a match
    for _ in range(366 * 24 * 60):
        if (
            dt.month in months
            and dt.day in doms
            and dt.weekday() in _convert_dow(dows)
            and dt.hour in hours
            and dt.minute in minutes
        ):
            return dt
        dt += timedelta(minutes=1)

    raise ValueError(f"No matching time found within 1 year for: {expr!r}")


def _convert_dow(cron_dows: set[int]) -> set[int]:
    """Convert cron dow (0=Sun, 6=Sat) to Python weekday (0=Mon, 6=Sun)."""
    mapping = {0: 6, 1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5}
    return {mapping[d] for d in cron_dows}


def describe(expr: str) -> str:
    """Return a human-readable description of a cron expression."""
    fields = expr.strip().split()
    if len(fields) != 5:
        return expr

    minute, hour, dom, month, dow = fields

    # Common patterns
    if expr.strip() == "* * * * *":
        return "Every minute"
    if minute != "*" and hour == "*" and dom == "*" and month == "*" and dow == "*":
        return f"Every hour at minute {minute}"
    if minute != "*" and hour != "*" and dom == "*" and month == "*" and dow == "*":
        return f"Daily at {int(hour):02d}:{int(minute):02d}"
    if minute != "*" and hour != "*" and dom == "*" and month == "*" and dow == "1-5":
        return f"Weekdays at {int(hour):02d}:{int(minute):02d}"
    if minute != "*" and hour != "*" and dom == "*" and month == "*" and dow != "*":
        day_names = {0: "Sun", 1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat"}
        try:
            day = day_names.get(int(dow), dow)
            return f"Weekly on {day} at {int(hour):02d}:{int(minute):02d}"
        except ValueError:
            pass
    if minute != "*" and hour != "*" and dom != "*" and month == "*" and dow == "*":
        return f"Monthly on day {dom} at {int(hour):02d}:{int(minute):02d}"

    return expr
