from __future__ import annotations

from dataclasses import dataclass

import requests

from icalnotifier.meetings import Event, dedupe_events, parse_calendar


@dataclass(slots=True)
class FetchResult:
    events: list[Event]
    errors: list[str]


def fetch_events(urls: list[str], timeout_seconds: int = 20) -> FetchResult:
    if not urls:
        return FetchResult(events=[], errors=[])

    events: list[Event] = []
    errors: list[str] = []
    for url in urls:
        try:
            response = requests.get(url, timeout=timeout_seconds)
            response.raise_for_status()
            events.extend(parse_calendar(response.text, url))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{url}: {exc}")
    return FetchResult(events=dedupe_events(events), errors=errors)
