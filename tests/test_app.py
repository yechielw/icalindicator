from datetime import UTC, datetime

from icalnotifier.app import format_indicator_time
from icalnotifier.meetings import Event


def make_event(dt: datetime) -> Event:
    return Event(
        title="Test",
        start=dt,
        end=None,
        meeting_url=None,
        source_url="https://example.com/calendar.ics",
    )


def test_indicator_time_shows_minutes_for_under_one_hour() -> None:
    now = datetime(2026, 3, 12, 10, 0, tzinfo=UTC)
    event = make_event(datetime(2026, 3, 12, 10, 45, tzinfo=UTC))
    assert format_indicator_time(event, now) == "45m"


def test_indicator_time_shows_clock_time_for_later_today() -> None:
    now = datetime(2026, 3, 12, 10, 0, tzinfo=UTC)
    event = make_event(datetime(2026, 3, 12, 12, 30, tzinfo=UTC))
    assert format_indicator_time(event, now) == "12:30"


def test_indicator_time_shows_tomorrow() -> None:
    now = datetime(2026, 3, 12, 10, 0, tzinfo=UTC)
    event = make_event(datetime(2026, 3, 13, 8, 0, tzinfo=UTC))
    assert format_indicator_time(event, now) == "tmr"


def test_indicator_time_shows_weekday_later_this_week() -> None:
    now = datetime(2026, 3, 12, 10, 0, tzinfo=UTC)
    event = make_event(datetime(2026, 3, 14, 8, 0, tzinfo=UTC))
    assert format_indicator_time(event, now) == "Sat"


def test_indicator_time_shows_date_for_next_week_or_later() -> None:
    now = datetime(2026, 3, 12, 10, 0, tzinfo=UTC)
    event = make_event(datetime(2026, 3, 20, 8, 0, tzinfo=UTC))
    assert format_indicator_time(event, now) == "03\n20"
