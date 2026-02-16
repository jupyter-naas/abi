import select
import subprocess
import threading
import time
import webbrowser
from collections import deque

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, Static

from .stack_runtime import (
    ComposeServiceState,
    compose_service_list,
    compose_service_states,
    run_compose,
)
from .stack_services import ReadinessResult, SERVICE_CATALOG, evaluate_service_readiness


class StackTextualApp(App[None]):
    CSS = """
    Screen {
        layout: vertical;
    }

    #body {
        height: 1fr;
    }

    #services {
        width: 38%;
        border: round #2f6db4;
    }

    #right {
        width: 62%;
    }

    #selected {
        height: 11;
        border: round #1f8f5f;
        padding: 0 1;
    }

    #logs {
        height: 1fr;
        border: round #8b4da9;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("j,down", "cursor_down", "Down"),
        Binding("k,up", "cursor_up", "Up"),
        Binding("u", "up_service", "Up service"),
        Binding("U", "up_stack", "Up stack"),
        Binding("r", "restart_service", "Restart"),
        Binding("s,S", "stop_service", "Stop"),
        Binding("d", "down_service", "Down service"),
        Binding("D", "down_stack", "Down -v"),
        Binding("o", "open_url", "Open URL"),
        Binding("p", "toggle_pause", "Pause"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, refresh_interval: float = 1.5):
        super().__init__()
        self.refresh_interval = max(0.5, refresh_interval)

        self.services: list[str] = []
        self.selected_index = 0
        self.paused = False
        self.states_by_name: dict[str, ComposeServiceState] = {}
        self.readiness_by_name: dict[str, ReadinessResult] = {}
        self.logs_text = ""
        self.action_status = ""
        self.last_error: str | None = None

        self._services_refresh_interval = 15.0
        self._probe_refresh_interval = 1.2
        self._selected_probe_refresh_interval = 0.25
        self._probe_http_timeout = 0.35
        self._probe_tcp_timeout = 0.30
        self._logs_poll_interval = 0.2

        self._selected_service_for_logs: str | None = None
        self._logs_follow_process: subprocess.Popen[str] | None = None
        self._logs_cache_by_service: dict[str, deque[str]] = {}
        self._logs_buffer: deque[str] = deque(maxlen=320)

        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._dirty = True

        self._snapshot_thread: threading.Thread | None = None
        self._logs_thread: threading.Thread | None = None
        self._probe_threads_by_service: dict[str, threading.Thread] = {}
        self._action_thread: threading.Thread | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal(id="body"):
            yield DataTable(id="services")
            with Vertical(id="right"):
                yield Static(id="selected")
                yield Static(id="logs")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#services", DataTable)
        table.add_columns("Service", "State", "Ready")
        table.cursor_type = "row"
        table.zebra_stripes = True

        self._snapshot_thread = threading.Thread(
            target=self._snapshot_worker, daemon=True
        )
        self._logs_thread = threading.Thread(target=self._logs_worker, daemon=True)
        self._snapshot_thread.start()
        self._logs_thread.start()

        self.set_interval(1 / 24, self._refresh_ui)

    def on_unmount(self) -> None:
        self._stop_event.set()
        self._stop_logs_follow_process()

    def _mark_dirty(self) -> None:
        with self._lock:
            self._dirty = True

    def _selected_service_locked(self) -> str | None:
        if not self.services:
            return None
        if self.selected_index >= len(self.services):
            self.selected_index = len(self.services) - 1
        return self.services[self.selected_index]

    def _selected_service(self) -> str | None:
        with self._lock:
            return self._selected_service_locked()

    def _set_selected_index_locked(self, new_index: int) -> None:
        if not self.services:
            return
        bounded_index = max(0, min(new_index, len(self.services) - 1))
        if bounded_index == self.selected_index:
            return
        self.selected_index = bounded_index
        selected = self._selected_service_locked()
        if selected is not None:
            cached = self._logs_cache_by_service.get(selected)
            self.logs_text = "\n".join(cached) if cached else "Loading logs..."
        self._dirty = True

    def _interruptible_wait(self, timeout: float, step: float = 0.08) -> bool:
        remaining = max(0.0, timeout)
        while remaining > 0:
            wait_for = min(step, remaining)
            if self._stop_event.wait(wait_for):
                return True
            remaining -= wait_for
        return False

    def _state_style(self, state_label: str) -> str:
        if state_label == "running":
            return "green"
        if state_label in ("exited", "dead", "failed"):
            return "red"
        if state_label in ("restarting", "paused"):
            return "yellow"
        if state_label in ("created", "not-created", "unknown"):
            return "bright_black"
        return "white"

    def _ready_markup(self, readiness: ReadinessResult | None) -> str:
        if readiness is None:
            return "[yellow]...[/]"
        if readiness.ready:
            return "[green]yes[/]"
        return "[red]no[/]"

    def _ensure_probe_workers_locked(self) -> None:
        for service_name in self.services:
            if service_name in self._probe_threads_by_service:
                continue
            thread = threading.Thread(
                target=self._probe_service_worker,
                args=(service_name,),
                daemon=True,
            )
            self._probe_threads_by_service[service_name] = thread
            thread.start()

    def _snapshot_worker(self) -> None:
        last_services_refresh_at = 0.0
        while not self._stop_event.is_set():
            try:
                now = time.monotonic()
                states = compose_service_states()
                discovered_services: list[str] = []
                if now - last_services_refresh_at >= self._services_refresh_interval:
                    discovered_services = compose_service_list()
                    last_services_refresh_at = now

                with self._lock:
                    merged_services = (
                        set(self.services)
                        | set(discovered_services)
                        | set(states.keys())
                        | set(SERVICE_CATALOG.keys())
                    )
                    self.services = sorted(merged_services)
                    self.states_by_name = states
                    self._ensure_probe_workers_locked()
                    self.last_error = None
                    self._dirty = True
            except Exception as error:  # pragma: no cover
                with self._lock:
                    self.last_error = str(error)
                    self._dirty = True

            if self._stop_event.wait(self.refresh_interval):
                return

    def _probe_service_worker(self, service_name: str) -> None:
        while not self._stop_event.is_set():
            with self._lock:
                state = self.states_by_name.get(service_name)
                selected = self._selected_service_locked()

            try:
                readiness = evaluate_service_readiness(
                    service_name,
                    state,
                    http_timeout=self._probe_http_timeout,
                    tcp_timeout=self._probe_tcp_timeout,
                )
            except Exception as error:  # pragma: no cover
                readiness = ReadinessResult(False, "probe", str(error))

            with self._lock:
                self.readiness_by_name[service_name] = readiness
                self._dirty = True

            interval = (
                self._selected_probe_refresh_interval
                if selected == service_name
                else self._probe_refresh_interval
            )
            if self._interruptible_wait(interval):
                return

    def _stop_logs_follow_process(self) -> None:
        process = self._logs_follow_process
        self._logs_follow_process = None
        if process is None:
            return
        try:
            process.terminate()
            process.wait(timeout=0.5)
        except Exception:  # pragma: no cover
            try:
                process.kill()
            except Exception:
                pass

    def _start_logs_follow_process(self, service_name: str) -> None:
        self._stop_logs_follow_process()
        self._logs_follow_process = subprocess.Popen(
            [
                "docker",
                "compose",
                "logs",
                "-f",
                "--no-color",
                "--tail=80",
                service_name,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

    def _logs_worker(self) -> None:
        while not self._stop_event.is_set():
            with self._lock:
                selected = self._selected_service_locked()
                selected_state = self.states_by_name.get(selected) if selected else None
                selected_changed = selected != self._selected_service_for_logs

            if selected is None:
                self._stop_logs_follow_process()
                with self._lock:
                    self.logs_text = ""
                    self._selected_service_for_logs = None
                    self._logs_buffer.clear()
                    self._dirty = True
                if self._stop_event.wait(self._logs_poll_interval):
                    return
                continue

            if selected_changed:
                with self._lock:
                    cached = self._logs_cache_by_service.get(selected)
                    if cached is None:
                        cached = deque(maxlen=320)
                        self._logs_cache_by_service[selected] = cached
                    self._logs_buffer = cached
                    self.logs_text = "\n".join(cached) if cached else "Loading logs..."
                    self._selected_service_for_logs = selected
                    self._dirty = True

            running = selected_state is not None and selected_state.state == "running"
            if not running:
                self._stop_logs_follow_process()
                try:
                    result = run_compose(
                        ["logs", "--no-color", "--tail=120", selected],
                        capture_output=True,
                    )
                    logs_text = result.stdout.strip() or "No container logs yet."
                except Exception as error:  # pragma: no cover
                    logs_text = f"No container logs yet ({error})"
                with self._lock:
                    self.logs_text = logs_text
                    self._dirty = True
                if self._stop_event.wait(max(self._logs_poll_interval, 1.0)):
                    return
                continue

            if selected_changed or self._logs_follow_process is None:
                try:
                    self._start_logs_follow_process(selected)
                except Exception as error:  # pragma: no cover
                    with self._lock:
                        self.logs_text = f"Failed to stream logs: {error}"
                        self._dirty = True
                    if self._stop_event.wait(0.5):
                        return
                    continue

            process = self._logs_follow_process
            if process is None or process.stdout is None:
                if self._stop_event.wait(self._logs_poll_interval):
                    return
                continue

            ready, _, _ = select.select(
                [process.stdout], [], [], self._logs_poll_interval
            )
            if not ready:
                if process.poll() is not None:
                    self._stop_logs_follow_process()
                continue

            line = process.stdout.readline()
            if line == "":
                if process.poll() is not None:
                    self._stop_logs_follow_process()
                continue

            with self._lock:
                self._logs_buffer.append(line.rstrip("\n"))
                self.logs_text = "\n".join(self._logs_buffer)
                if self._selected_service_for_logs is not None:
                    self._logs_cache_by_service[self._selected_service_for_logs] = (
                        self._logs_buffer
                    )
                self._dirty = True

    def _start_action(self, label: str, args: list[str]) -> None:
        with self._lock:
            if self._action_thread is not None and self._action_thread.is_alive():
                self.action_status = "Action already running..."
                self._dirty = True
                return
            self.action_status = f"{label}..."
            self._dirty = True

        def _action_worker() -> None:
            try:
                run_compose(args)
                status = f"{label} done"
            except Exception as error:  # pragma: no cover
                status = f"{label} failed: {error}"
            with self._lock:
                self.action_status = status
                self._dirty = True

        thread = threading.Thread(target=_action_worker, daemon=True)
        self._action_thread = thread
        thread.start()

    def action_cursor_down(self) -> None:
        with self._lock:
            if not self.services:
                return
            self._set_selected_index_locked(self.selected_index + 1)

    def action_cursor_up(self) -> None:
        with self._lock:
            if not self.services:
                return
            self._set_selected_index_locked(self.selected_index - 1)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.id != "services":
            return
        with self._lock:
            self._set_selected_index_locked(event.cursor_row)

    def action_toggle_pause(self) -> None:
        with self._lock:
            self.paused = not self.paused
            self._dirty = True

    def action_restart_service(self) -> None:
        selected = self._selected_service()
        if selected is not None:
            self._start_action(f"Restarting {selected}", ["restart", selected])

    def action_up_service(self) -> None:
        selected = self._selected_service()
        if selected is not None:
            self._start_action(f"Starting {selected}", ["up", "-d", selected])

    def action_up_stack(self) -> None:
        self._start_action("Starting stack", ["up", "-d"])

    def action_stop_service(self) -> None:
        selected = self._selected_service()
        if selected is not None:
            self._start_action(f"Stopping {selected}", ["stop", selected])

    def action_down_service(self) -> None:
        selected = self._selected_service()
        if selected is not None:
            self._start_action(f"Downing {selected}", ["rm", "-s", "-f", selected])

    def action_down_stack(self) -> None:
        self._start_action("Downing stack with volumes", ["down", "-v"])

    def action_open_url(self) -> None:
        selected = self._selected_service()
        if selected is None:
            return
        service_def = SERVICE_CATALOG.get(selected)
        if service_def and service_def.urls:
            webbrowser.open(service_def.urls[0])

    def _refresh_ui(self) -> None:
        with self._lock:
            dirty = self._dirty
            paused = self.paused
            services = list(self.services)
            selected_index = self.selected_index
            states = dict(self.states_by_name)
            readiness = dict(self.readiness_by_name)
            logs_text = self.logs_text
            action_status = self.action_status
            last_error = self.last_error
            if dirty:
                self._dirty = False

        if not dirty or paused:
            return

        table = self.query_one("#services", DataTable)
        selected_widget = self.query_one("#selected", Static)
        logs_widget = self.query_one("#logs", Static)

        table.clear()
        for service in services:
            state = states.get(service)
            state_label = state.state if state is not None else "not-created"
            table.add_row(
                service,
                f"[{self._state_style(state_label)}]{state_label}[/]",
                self._ready_markup(readiness.get(service)),
            )

        if services:
            if selected_index >= len(services):
                selected_index = len(services) - 1
            table.move_cursor(row=selected_index, column=0, animate=False)

        selected_service = services[selected_index] if services else None
        if selected_service is None:
            selected_widget.update("No service available")
        else:
            selected_state = states.get(selected_service)
            selected_ready = readiness.get(selected_service)
            service_def = SERVICE_CATALOG.get(selected_service)
            state_label = selected_state.state if selected_state else "not-created"
            ready_line = "ready: ..."
            detail_line = "detail: probing..."
            if selected_ready is not None:
                ready_value = "yes" if selected_ready.ready else "no"
                ready_style = "green" if selected_ready.ready else "red"
                ready_line = f"ready: [{ready_style}]{ready_value}[/] via {selected_ready.source}"
                detail_line = f"detail: {selected_ready.detail}"

            lines = [
                f"service: {selected_service}",
                f"state: [{self._state_style(state_label)}]{state_label}[/]",
                "health: "
                + (
                    selected_state.health
                    if selected_state and selected_state.health
                    else "-"
                ),
                ready_line,
                detail_line,
            ]
            if service_def and service_def.urls:
                lines.append(f"url: {service_def.urls[0]}")
            selected_widget.update("\n".join(lines))

        logs_widget.update(logs_text or "No logs yet")

        footer = ""
        if action_status:
            if "failed" in action_status.lower():
                footer = f"[red]{action_status}[/]"
            elif "done" in action_status.lower():
                footer = f"[green]{action_status}[/]"
            else:
                footer = f"[yellow]{action_status}[/]"
        if last_error:
            selected_widget.update(f"[red]Docker Error[/]\n{last_error}")
        if footer:
            self.sub_title = footer
        else:
            self.sub_title = ""


class StackTUI:
    def __init__(self, refresh_interval: float = 1.5):
        self.refresh_interval = refresh_interval

    def run(self) -> None:
        StackTextualApp(refresh_interval=self.refresh_interval).run()
