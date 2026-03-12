from icalnotifier.config import Settings


def test_settings_from_dict_normalizes_urls() -> None:
    settings = Settings.from_dict(
        {"ics_urls": [" https://example.com/a.ics ", "", "https://example.com/b.ics"]}
    )
    assert settings.ics_urls == ["https://example.com/a.ics", "https://example.com/b.ics"]
    assert settings.notification_minutes == 10


def test_app_module_imports() -> None:
    import icalnotifier.app  # noqa: F401
