from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from PySide6.QtCore import QObject, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QColor, QDesktopServices, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSystemTrayIcon,
    QVBoxLayout,
)

from icalnotifier.config import Settings, load_settings, save_settings
from icalnotifier.fetcher import FetchResult, fetch_events
from icalnotifier.meetings import Event


@dataclass(slots=True)
class RuntimeState:
    settings: Settings
    events: list[Event] = field(default_factory=list)
    last_error: str | None = None
    last_notified_key: tuple[str, datetime] | None = None

    def today_events(self) -> list[Event]:
        today = datetime.now().astimezone().date()
        return [event for event in self.events if event.start.astimezone().date() == today]

    def next_event(self) -> Event | None:
        now = datetime.now(UTC)
        candidates = [event for event in self.events if event.start >= now]
        return min(candidates, key=lambda item: item.start, default=None)

    def next_countdown(self) -> timedelta | None:
        next_event = self.next_event()
        if next_event is None:
            return None
        return next_event.start - datetime.now(UTC)


def format_indicator_time(next_event: Event | None, now: datetime | None = None) -> str:
    if next_event is None:
        return "--"

    current = (now or datetime.now(UTC)).astimezone()
    start = next_event.start.astimezone()
    delta = start - current
    if start.date() == current.date():
        if timedelta() <= delta < timedelta(hours=1):
            return f"{max(0, int(delta.total_seconds() // 60))}m"
        return start.strftime("%H:%M")

    if start.date() == current.date() + timedelta(days=1):
        return "tmr"

    current_week_start = current.date() - timedelta(days=current.weekday())
    next_week_start = current_week_start + timedelta(days=7)
    if start.date() < next_week_start:
        return start.strftime("%a")

    return start.strftime("%m-%d")


def build_tray_icon(text: str) -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor(0, 0, 0, 0))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#1f2933"))
    painter.setPen(QColor("#1f2933"))
    painter.drawRoundedRect(2, 2, 60, 60, 14, 14)

    painter.setPen(QColor("#f5f7fa"))
    font = QFont("DejaVu Sans", 18 if len(text) > 4 else 24)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), 0x84, text)
    painter.end()
    return QIcon(pixmap)


def open_in_browser(event: Event | None) -> None:
    if event is None or not event.meeting_url:
        return
    QDesktopServices.openUrl(QUrl(event.meeting_url))


class SettingsDialog(QDialog):
    settings_saved = Signal(Settings)

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.setWindowTitle("icalnotifier settings")
        self.setMinimumWidth(520)

        self.urls = QPlainTextEdit()
        self.urls.setPlaceholderText("One ICS URL per line")
        self.urls.setPlainText("\n".join(settings.ics_urls))

        self.notification_minutes = QSpinBox()
        self.notification_minutes.setRange(0, 240)
        self.notification_minutes.setValue(settings.notification_minutes)

        form = QFormLayout()
        form.addRow("ICS URLs", self.urls)
        form.addRow("Notify before (minutes)", self.notification_minutes)

        save_button = QPushButton("Save")
        cancel_button = QPushButton("Cancel")
        save_button.clicked.connect(self._save)
        cancel_button.clicked.connect(self.reject)

        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(cancel_button)
        row.addWidget(save_button)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addLayout(row)
        self.setLayout(layout)

    def _save(self) -> None:
        settings = Settings(
            ics_urls=[line.strip() for line in self.urls.toPlainText().splitlines() if line.strip()],
            notification_minutes=self.notification_minutes.value(),
        )
        self.settings_saved.emit(settings)
        self.accept()


class EventsDialog(QDialog):
    def __init__(self, state: RuntimeState, on_open_next, on_open_settings, on_refresh) -> None:
        super().__init__()
        self.setWindowTitle("icalnotifier")
        self.setMinimumWidth(560)
        self.setMinimumHeight(420)
        self._state = state
        self._on_open_next = on_open_next

        layout = QVBoxLayout()

        next_event = state.next_event()
        heading = "No upcoming meetings" if next_event is None else f"Next: {next_event.title}"
        heading_label = QLabel(heading)
        layout.addWidget(heading_label)

        if next_event is not None:
            subtitle = QLabel(
                f"{next_event.start.astimezone():%Y-%m-%d %H:%M}  |  {format_indicator_time(next_event)}"
            )
            layout.addWidget(subtitle)

        list_title = QLabel("Today's events")
        layout.addWidget(list_title)

        self.events_list = QListWidget()
        self._populate_events()
        self.events_list.itemActivated.connect(self._open_selected_event)
        layout.addWidget(self.events_list)

        if state.last_error:
            error_label = QLabel(f"Last fetch error: {state.last_error}")
            layout.addWidget(error_label)

        row = QHBoxLayout()
        open_next = QPushButton("Open next meeting")
        settings = QPushButton("Settings")
        refresh = QPushButton("Refresh")
        close = QPushButton("Close")

        open_next.setEnabled(bool(next_event and next_event.meeting_url))
        open_next.clicked.connect(on_open_next)
        settings.clicked.connect(on_open_settings)
        refresh.clicked.connect(on_refresh)
        close.clicked.connect(self.close)

        row.addWidget(open_next)
        row.addWidget(settings)
        row.addWidget(refresh)
        row.addStretch(1)
        row.addWidget(close)
        layout.addLayout(row)
        self.setLayout(layout)

    def _populate_events(self) -> None:
        self.events_list.clear()
        now = datetime.now(UTC)
        events_today = self._state.today_events()
        if not events_today:
            item = QListWidgetItem("No events today")
            item.setFlags(item.flags() & ~0x20)
            self.events_list.addItem(item)
            return
        for event in events_today:
            minutes = int((event.start - now).total_seconds() // 60)
            suffix = f" ({minutes}m)" if minutes >= 0 else " (live)"
            item = QListWidgetItem(f"{event.start.astimezone():%H:%M} {event.title}{suffix}")
            item.setData(0x0100, event)
            if not event.meeting_url:
                item.setFlags(item.flags() & ~0x20)
            self.events_list.addItem(item)

    def _open_selected_event(self, item: QListWidgetItem) -> None:
        event = item.data(0x0100)
        if event is not None:
            open_in_browser(event)


class FetchWorker(QObject):
    finished = Signal(object)

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self._settings = settings

    def run(self) -> None:
        self.finished.emit(fetch_events(self._settings.ics_urls))


class NotifierApp(QObject):
    def __init__(self, app: QApplication) -> None:
        super().__init__()
        self.app = app
        self.state = RuntimeState(load_settings())
        self.tray = QSystemTrayIcon()
        self.settings_dialog: SettingsDialog | None = None
        self.events_dialog: EventsDialog | None = None
        self._active_thread: QThread | None = None
        self._active_worker: FetchWorker | None = None

        self.tray.activated.connect(self._handle_tray_activation)
        self._refresh_tray()
        self.tray.show()

        self.fetch_timer = QTimer(self)
        self.fetch_timer.timeout.connect(self.refresh_events)
        self.fetch_timer.start(self.state.settings.poll_seconds * 1000)

        self.notify_timer = QTimer(self)
        self.notify_timer.timeout.connect(self._maybe_notify)
        self.notify_timer.start(15_000)

        QTimer.singleShot(0, self.refresh_events)
        if not self.state.settings.ics_urls:
            QTimer.singleShot(0, self.open_settings)

    def refresh_events(self) -> None:
        if self._active_thread is not None:
            return
        thread = QThread(self)
        worker = FetchWorker(self.state.settings)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_fetch_complete)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_active_thread)
        self._active_thread = thread
        self._active_worker = worker
        thread.start()

    def _clear_active_thread(self) -> None:
        self._active_thread = None
        self._active_worker = None

    def _on_fetch_complete(self, result: FetchResult) -> None:
        self.state.events = result.events
        self.state.last_error = result.errors[0] if result.errors else None
        self._refresh_tray()
        self._maybe_notify()

    def _refresh_tray(self) -> None:
        next_event = self.state.next_event()
        badge = format_indicator_time(next_event)
        self.tray.setIcon(build_tray_icon(badge))

        if not self.state.settings.ics_urls:
            self.tray.setToolTip("icalnotifier: configure calendars")
        elif next_event is None:
            self.tray.setToolTip("No upcoming meetings")
        else:
            self.tray.setToolTip(f"{next_event.title} at {next_event.start.astimezone():%Y-%m-%d %H:%M}")

    def _handle_tray_activation(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if not self.state.settings.ics_urls:
                self.open_settings()
                return
            open_in_browser(self.state.next_event())
            return
        if reason == QSystemTrayIcon.ActivationReason.MiddleClick:
            self.open_events()
            return

    def open_settings(self) -> None:
        if self.settings_dialog is not None and self.settings_dialog.isVisible():
            self.settings_dialog.raise_()
            self.settings_dialog.activateWindow()
            return
        self.settings_dialog = SettingsDialog(self.state.settings)
        self.settings_dialog.settings_saved.connect(self._save_settings)
        self.settings_dialog.show()

    def open_events(self) -> None:
        if self.events_dialog is not None and self.events_dialog.isVisible():
            self.events_dialog.raise_()
            self.events_dialog.activateWindow()
            return
        self.events_dialog = EventsDialog(
            self.state,
            lambda: open_in_browser(self.state.next_event()),
            self.open_settings,
            self.refresh_events,
        )
        self.events_dialog.show()

    def _save_settings(self, settings: Settings) -> None:
        self.state.settings = settings
        save_settings(settings)
        self.refresh_events()
        self._refresh_tray()

    def _maybe_notify(self) -> None:
        next_event = self.state.next_event()
        if next_event is None:
            return

        now = datetime.now(UTC)
        notification_time = next_event.start - timedelta(minutes=self.state.settings.notification_minutes)
        if now < notification_time or now > next_event.start:
            return

        key = (next_event.title, next_event.start)
        if self.state.last_notified_key == key:
            return

        body = f"{next_event.title} starts at {next_event.start.astimezone():%H:%M}"
        if next_event.meeting_url:
            body += "\nLeft click the tray icon to open the meeting."

        notify_send = shutil.which("notify-send")
        if notify_send is not None:
            subprocess.run([notify_send, "Upcoming meeting", body], check=False)

        canberra = shutil.which("canberra-gtk-play")
        if canberra is not None:
            subprocess.run([canberra, "-i", "bell"], check=False)

        self.state.last_notified_key = key


def _force_wayland_if_available() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "wayland;xcb")


def main() -> int:
    _force_wayland_if_available()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    notifier = NotifierApp(app)
    signal_timer = QTimer()
    signal_timer.start(250)
    signal_timer.timeout.connect(lambda: None)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
