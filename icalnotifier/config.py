from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from platformdirs import user_cache_dir, user_config_dir


DEFAULT_POLL_SECONDS = 60


@dataclass(slots=True)
class Settings:
    ics_urls: list[str] = field(default_factory=list)
    notification_minutes: int = 10
    poll_seconds: int = DEFAULT_POLL_SECONDS

    @classmethod
    def from_dict(cls, data: dict) -> "Settings":
        urls = data.get("ics_urls") or []
        if isinstance(urls, str):
            urls = [urls]
        return cls(
            ics_urls=[str(url).strip() for url in urls if str(url).strip()],
            notification_minutes=max(0, int(data.get("notification_minutes", 10))),
            poll_seconds=DEFAULT_POLL_SECONDS,
        )


def config_dir() -> Path:
    return Path(user_config_dir("icalnotifier"))


def config_path() -> Path:
    return config_dir() / "settings.json"


def cache_dir() -> Path:
    return Path(user_cache_dir("icalnotifier"))


def state_path() -> Path:
    return cache_dir() / "state.json"


def load_settings() -> Settings:
    path = config_path()
    if not path.exists():
        return Settings()
    data = json.loads(path.read_text(encoding="utf-8"))
    return Settings.from_dict(data)


def save_settings(settings: Settings) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
