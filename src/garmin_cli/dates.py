import re
from datetime import date, timedelta

from garmin_cli.output import UsageError

_OFFSET = re.compile(r"^([+-]\d+)([dw])$")


def parse_date(text: str, *, today: date | None = None) -> date:
    today = today or date.today()
    text = text.strip().lower()
    if text == "today":
        return today
    if text == "yesterday":
        return today - timedelta(days=1)
    m = _OFFSET.match(text)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        days = n * (7 if unit == "w" else 1)
        return today + timedelta(days=days)
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise UsageError(f"invalid date: {text!r}") from None


def _looks_like_iso_datetime(text: str) -> bool:
    # Guard against ever being handed a time component; ranges use bare dates only.
    return "T" in text


def parse_range(text: str, *, today: date | None = None) -> tuple[date, date]:
    text = text.strip()
    if ":" in text and not _looks_like_iso_datetime(text):
        start_s, end_s = text.split(":", 1)
        return parse_date(start_s, today=today), parse_date(end_s, today=today)
    single = parse_date(text, today=today)
    return single, single
