from datetime import UTC, datetime

from icalnotifier.meetings import extract_meeting_url, parse_calendar


def test_extract_meeting_url_from_text() -> None:
    url = extract_meeting_url("Join at https://meet.google.com/abc-defg-hij now")
    assert url == "https://meet.google.com/abc-defg-hij"


def test_parse_calendar_extracts_event_and_url() -> None:
    content = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
DTSTART:20260312T150000Z
DTEND:20260312T153000Z
SUMMARY:Standup
DESCRIPTION:https://teams.microsoft.com/l/meetup-join/example
END:VEVENT
END:VCALENDAR
"""
    events = parse_calendar(content, "https://example.com/calendar.ics")
    assert len(events) == 1
    assert events[0].title == "Standup"
    assert events[0].meeting_url == "https://teams.microsoft.com/l/meetup-join/example"
    assert events[0].start == datetime(2026, 3, 12, 15, 0, tzinfo=UTC)
