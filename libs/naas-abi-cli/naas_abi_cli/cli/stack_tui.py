import select
import sys
import termios
import threading
import time
import tty
import webbrowser
from contextlib import contextmanager

from rich.console import Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .stack_runtime import (
    ComposeServiceState,
    compose_service_list,
    compose_service_logs,
    compose_service_states,
)
from .stack_services import ReadinessResult, SERVICE_CATALOG, evaluate_service_readiness


@contextmanager
def _raw_keyboard_mode():
    if not sys.stdin.isatty():
        yield
        return

    file_descriptor = sys.stdin.fileno()
    old_settings = termios.tcgetattr(file_descriptor)
    try:
        tty.setcbreak(file_descriptor)
        yield
    finally:
        termios.tcsetattr(file_descriptor, termios.TCSADRAIN, old_settings)


class StackTUI:
    def __init__(self, refresh_interval: float = 1.5):
        self.refresh_interval = max(0.5, refresh_interval)
        self.max_fps = 24.0
        self.min_frame_interval = 1.0 / self.max_fps
        self.selected_index = 0
        self.paused = False
        self.services: list[str] = []
        self.states_by_name: dict[str, ComposeServiceState] = {}
        self.readiness_by_name: dict[str, ReadinessResult] = {}
        self.logs_text = ""
        self.last_error: str | None = None

        self._services_refresh_interval = 15.0
        self._probe_refresh_interval = 0.25
        self._logs_refresh_interval = 2.0
        self._last_logs_refresh_at = 0.0
        self._selected_service_for_logs: str | None = None

        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._probe_now_event = threading.Event()
        self._state_changed_event = threading.Event()
        self._threads: list[threading.Thread] = []

    def _start_workers(self) -> None:
        self._threads = [
            threading.Thread(target=self._snapshot_worker, daemon=True),
            threading.Thread(target=self._probe_worker, daemon=True),
            threading.Thread(target=self._logs_worker, daemon=True),
        ]
        for thread in self._threads:
            thread.start()

    def _stop_workers(self) -> None:
        self._stop_event.set()
        self._probe_now_event.set()
        for thread in self._threads:
            thread.join(timeout=1.0)

    def _snapshot_worker(self) -> None:
        last_services_refresh_at = 0.0
        while not self._stop_event.is_set():
            try:
                now = time.monotonic()
                states = compose_service_states()

                discovered_services: list[str] = []
                if (
                    now - last_services_refresh_at >= self._services_refresh_interval
                    or not self.services
                ):
                    discovered_services = compose_service_list()
                    last_services_refresh_at = now

                with self._lock:
                    self.states_by_name = states
                    merged_services = (
                        set(self.services)
                        | set(discovered_services)
                        | set(states.keys())
                        | set(SERVICE_CATALOG.keys())
                    )
                    self.services = sorted(merged_services)
                    self.last_error = None
                self._state_changed_event.set()
            except Exception as error:  # pragma: no cover - terminal runtime fallback
                with self._lock:
                    self.last_error = str(error)
                self._state_changed_event.set()

            if self._stop_event.wait(self.refresh_interval):
                return

    def _probe_worker(self) -> None:
        index = 0
        while not self._stop_event.is_set():
            with self._lock:
                services = list(self.services)
                states = dict(self.states_by_name)
                selected_service = self._selected_service_locked()

            if not services:
                if self._stop_event.wait(0.2):
                    return
                continue

            probe_selected_first = (
                self._probe_now_event.is_set() and selected_service is not None
            )
            if probe_selected_first:
                self._probe_now_event.clear()
                if selected_service is None:
                    if self._stop_event.wait(0.1):
                        return
                    continue
                service_name: str = selected_service
            else:
                service_name = services[index % len(services)]
                index += 1

            state = states.get(service_name)
            try:
                readiness = evaluate_service_readiness(service_name, state)
            except Exception as error:  # pragma: no cover - probe safety fallback
                readiness = ReadinessResult(False, "probe", str(error))

            with self._lock:
                self.readiness_by_name[service_name] = readiness
            self._state_changed_event.set()

            interval = 0.05 if probe_selected_first else self._probe_refresh_interval
            if self._stop_event.wait(interval):
                return

    def _logs_worker(self) -> None:
        while not self._stop_event.is_set():
            with self._lock:
                selected_service = self._selected_service_locked()
                selected_state = (
                    self.states_by_name.get(selected_service)
                    if selected_service is not None
                    else None
                )
                selected_changed = selected_service != self._selected_service_for_logs
                should_refresh_logs = selected_changed or (
                    time.monotonic() - self._last_logs_refresh_at
                    >= self._logs_refresh_interval
                )

            if selected_service is None:
                with self._lock:
                    self.logs_text = ""
                    self._selected_service_for_logs = None
                self._state_changed_event.set()
                if self._stop_event.wait(0.2):
                    return
                continue

            if selected_state is None:
                with self._lock:
                    self.logs_text = "No container logs yet."
                    self._selected_service_for_logs = selected_service
                    self._last_logs_refresh_at = time.monotonic()
                self._state_changed_event.set()
                if self._stop_event.wait(0.4):
                    return
                continue

            if should_refresh_logs:
                try:
                    logs_text = compose_service_logs(selected_service, tail=60)
                except Exception as error:  # pragma: no cover - runtime fallback
                    logs_text = f"Failed to read logs: {error}"

                with self._lock:
                    if self._selected_service_locked() == selected_service:
                        self.logs_text = logs_text
                    self._selected_service_for_logs = selected_service
                    self._last_logs_refresh_at = time.monotonic()
                self._state_changed_event.set()

            if self._stop_event.wait(0.2):
                return

    def run(self) -> None:
        self._start_workers()
        try:
            with (
                _raw_keyboard_mode(),
                Live(
                    self._render(),
                    refresh_per_second=self.max_fps,
                    screen=True,
                    auto_refresh=False,
                ) as live,
            ):
                last_render_at = 0.0
                while True:
                    key = self._read_key(timeout=self.min_frame_interval)
                    if key and self._handle_key(key):
                        return

                    if self.paused:
                        continue

                    now = time.monotonic()
                    frame_due = now - last_render_at >= self.min_frame_interval
                    if frame_due and self._state_changed_event.is_set():
                        self._state_changed_event.clear()
                        live.update(self._render(), refresh=True)
                        last_render_at = now
        finally:
            self._stop_workers()

    def _read_key(self, timeout: float = 0.0) -> str | None:
        if not sys.stdin.isatty():
            return None

        ready, _, _ = select.select([sys.stdin], [], [], max(0.0, timeout))
        if not ready:
            return None

        char = sys.stdin.read(1)
        if char == "\x1b":
            ready, _, _ = select.select([sys.stdin], [], [], 0.01)
            if ready:
                char += sys.stdin.read(1)
            ready, _, _ = select.select([sys.stdin], [], [], 0.01)
            if ready:
                char += sys.stdin.read(1)
        return char

    def _handle_key(self, key: str) -> bool:
        if key == "q":
            return True
        selection_changed = False

        if key in ("j", "\x1b[B"):
            with self._lock:
                if self.services:
                    previous_index = self.selected_index
                    self.selected_index = min(
                        self.selected_index + 1, len(self.services) - 1
                    )
                    selection_changed = self.selected_index != previous_index
        elif key in ("k", "\x1b[A"):
            with self._lock:
                previous_index = self.selected_index
                self.selected_index = max(self.selected_index - 1, 0)
                selection_changed = self.selected_index != previous_index
        elif key == "p":
            self.paused = not self.paused
            self._state_changed_event.set()
        elif key == "o":
            selected = self._selected_service()
            if selected is not None:
                service_def = SERVICE_CATALOG.get(selected)
                if service_def and service_def.urls:
                    webbrowser.open(service_def.urls[0])

        if selection_changed:
            with self._lock:
                self._last_logs_refresh_at = 0.0
            self._probe_now_event.set()
            self._state_changed_event.set()

        return False

    def _selected_service_locked(self) -> str | None:
        if not self.services:
            return None
        if self.selected_index >= len(self.services):
            self.selected_index = len(self.services) - 1
        return self.services[self.selected_index]

    def _selected_service(self) -> str | None:
        with self._lock:
            return self._selected_service_locked()

    def _render(self) -> Layout:
        with self._lock:
            services = list(self.services)
            states_by_name = dict(self.states_by_name)
            readiness_by_name = dict(self.readiness_by_name)
            logs_text = self.logs_text
            last_error = self.last_error
            selected_index = self.selected_index

        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body", ratio=1),
            Layout(name="footer", size=1),
        )
        layout["body"].split_row(
            Layout(name="services", ratio=2), Layout(name="details", ratio=3)
        )
        layout["details"].split_column(
            Layout(name="selected", ratio=2), Layout(name="logs", ratio=3)
        )

        header = Text("ABI Stack TUI", style="bold")
        layout["header"].update(Panel(header))

        if last_error:
            layout["services"].update(Panel("", title="Services"))
            layout["selected"].update(Panel(last_error, title="Docker Error"))
            layout["logs"].update(Panel("", title="Logs"))
            layout["footer"].update(Text("q quit | p pause", style="dim"))
            return layout

        table = Table(show_header=True, header_style="bold")
        table.add_column("Service")
        table.add_column("State")
        table.add_column("Ready")

        for index, service in enumerate(services):
            state = states_by_name.get(service)
            state_label = state.state if state is not None else "not-created"
            readiness = readiness_by_name.get(service)
            if readiness is None:
                ready_label = "..."
            else:
                ready_label = "yes" if readiness.ready else "no"
            style = "reverse" if index == selected_index else ""
            table.add_row(service, state_label, ready_label, style=style)

        layout["services"].update(Panel(table, title="Services"))

        selected_service = self._selected_service()
        if selected_service is None:
            layout["selected"].update(Panel("No service available"))
            layout["logs"].update(Panel(""))
            layout["footer"].update(Text("q quit", style="dim"))
            return layout

        selected_state = states_by_name.get(selected_service)
        selected_ready = readiness_by_name.get(selected_service)
        service_def = SERVICE_CATALOG.get(selected_service)

        ready_line = "ready: ..."
        detail_line = "detail: probing..."
        if selected_ready is not None:
            ready_line = f"ready: {'yes' if selected_ready.ready else 'no'} via {selected_ready.source}"
            detail_line = f"detail: {selected_ready.detail}"

        selected_rows = [
            Text(f"service: {selected_service}"),
            Text(f"state: {selected_state.state if selected_state else 'not-created'}"),
            Text(
                f"health: {selected_state.health if selected_state and selected_state.health else '-'}"
            ),
            Text(ready_line),
            Text(detail_line),
        ]
        if service_def and service_def.urls:
            selected_rows.append(Text("url: " + service_def.urls[0]))

        layout["selected"].update(
            Panel(Group(*selected_rows), title="Selected Service")
        )

        layout["logs"].update(Panel(logs_text or "No logs yet", title="Logs"))

        footer_text = "j/k or arrows move | o open URL | p pause | q quit"
        if self.paused:
            footer_text += " | paused"
        layout["footer"].update(Text(footer_text, style="dim"))
        return layout
