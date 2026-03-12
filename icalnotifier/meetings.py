from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterable

from icalendar import Calendar


MEETING_URL_RE = re.compile(
    r"https?://[^\s<>\"]*(?:meet\.google\.com|teams\.microsoft\.com|zoom\.us)[^\s<>\"]*",
    re.IGNORECASE,
)


@dataclass(slots=True, frozen=True)
class Event:
    title: str
    start: datetime
    end: datetime | None
    meeting_url: str | None
    source_url: str

    @property
    def sort_key(self) -> tuple[datetime, str]:
        return (self.start, self.title.lower())

    def to_dict(self) -> dict[str, str | None]:
        return {
            "title": self.title,
            "start": self.start.isoformat(),
            "end": self.end.isoformat() if self.end else None,
            "meeting_url": self.meeting_url,
            "source_url": self.source_url,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str | None]) -> "Event":
        end = data.get("end")
        return cls(
            title=str(data["title"]),
            start=datetime.fromisoformat(str(data["start"])).astimezone(UTC),
            end=datetime.fromisoformat(str(end)).astimezone(UTC) if end else None,
            meeting_url=str(data["meeting_url"]) if data.get("meeting_url") else None,
            source_url=str(data["source_url"]),
        )


def normalize_datetime(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def extract_meeting_url(*values: object) -> str | None:
    for value in values:
        if value is None:
            continue
        match = MEETING_URL_RE.search(str(value))
        if match:
            return match.group(0)
    return None


def parse_calendar(content: str, source_url: str) -> list[Event]:
    calendar = Calendar.from_ical(content)
    events: list[Event] = []
    for component in calendar.walk("VEVENT"):
        start = normalize_datetime(component.decoded("DTSTART", None))
        if start is None:
            continue
        end = normalize_datetime(component.decoded("DTEND", None))
        title = str(component.get("SUMMARY", "Untitled event")).strip() or "Untitled event"
        meeting_url = extract_meeting_url(
            component.get("URL"),
            component.get("LOCATION"),
            component.get("DESCRIPTION"),
        )
        events.append(
            Event(
                title=title,
                start=start,
                end=end,
                meeting_url=meeting_url,
                source_url=source_url,
            )
        )
    return sorted(events, key=lambda event: event.sort_key)


def dedupe_events(events: Iterable[Event]) -> list[Event]:
    seen: set[tuple[str, datetime]] = set()
    result: list[Event] = []
    for event in sorted(events, key=lambda item: item.sort_key):
        key = (event.title, event.start)
        if key in seen:
            continue
        seen.add(key)
        result.append(event)
    return result
