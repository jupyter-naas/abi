"""Keeps the registry's remote tools in line with the modules that serve them.

A module that declares tools publishes them in its discovery descriptor
(``docs/adr/20261022_remote-module-tools.md``). This service reads, on a schedule,
which modules have a ready instance and publishes their tools to the registry as
``<module_id>/<name>@<version>``; when the module has no ready instance any more
(stopped, draining, expired) it unpublishes them, and the index follows at the
registry's next search (``ToolRegistryService`` re-syncs whatever changed).

It never drops what it has on a failed read: discovery being unreachable says
nothing about the modules. A module whose id is a local module's name, or whose
tools another module already publishes, is skipped with a warning, so a remote
module cannot replace an in-process one.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Collection

from naas_abi_core.services.tool_registry.ToolRegistryPort import (
    IRemoteToolDirectory,
    IToolRegistry,
    PublishedTool,
    RemoteModuleTools,
    RemoteToolDirectoryError,
    ToolBinding,
    ToolDefinition,
    ToolRegistryError,
)
from naas_abi_core.utils.Logger import logger

BindingFactory = Callable[[ToolDefinition, int], ToolBinding]


def _fingerprint(module: RemoteModuleTools) -> tuple[int, tuple[str, ...]]:
    return (
        module.contract_major,
        tuple(
            sorted(definition.model_dump_json() for definition in module.definitions)
        ),
    )


class RemoteToolSynchronizer:
    def __init__(
        self,
        registry: IToolRegistry,
        directory: IRemoteToolDirectory,
        bind: BindingFactory,
        *,
        reserved: Collection[str] = (),
        refresh_seconds: float = 5.0,
    ) -> None:
        if refresh_seconds <= 0:
            raise ValueError("refresh_seconds must be positive")
        self._registry = registry
        self._directory = directory
        self._bind = bind
        self._reserved = frozenset(reserved)
        self._refresh = refresh_seconds
        # What this service published: module id -> fingerprint of its tools.
        self._published: dict[str, tuple[int, tuple[str, ...]]] = {}
        # What it refused, so a standing refusal is reported once, not per read.
        self._refused: dict[str, tuple[int, tuple[str, ...]]] = {}
        self._failing = False
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def published_modules(self) -> frozenset[str]:
        with self._lock:
            return frozenset(self._published)

    def sync_once(self) -> bool:
        """One read of the directory. Returns whether the registry changed."""
        with self._lock:
            try:
                modules = self._directory.list_modules()
            except RemoteToolDirectoryError as exc:
                if not self._failing:
                    logger.warning(
                        f"Remote tools: modules not listed, keeping what is published: {exc}"
                    )
                self._failing = True
                return False
            self._failing = False
            serving = {m.module_id: m for m in modules if m.definitions}
            changed = False
            for module_id in sorted(set(self._published) - set(serving)):
                self._registry.unpublish(module_id)
                del self._published[module_id]
                logger.info(f"Remote tools: module '{module_id}' stopped serving")
                changed = True
            for module_id in sorted(set(self._refused) - set(serving)):
                del self._refused[module_id]
            for module_id, module in sorted(serving.items()):
                changed |= self._publish(module_id, module)
            return changed

    def _publish(self, module_id: str, module: RemoteModuleTools) -> bool:
        fingerprint = _fingerprint(module)
        if self._published.get(module_id) == fingerprint:
            return False
        if self._refused.get(module_id) == fingerprint:
            return False
        if module_id in self._reserved:
            self._refused[module_id] = fingerprint
            logger.warning(
                f"Remote tools: module '{module_id}' has the name of a module loaded "
                "here; its remote tools are not published."
            )
            return False
        try:
            self._registry.publish(
                module_id,
                [
                    PublishedTool(
                        definition, self._bind(definition, module.contract_major)
                    )
                    for definition in module.definitions
                ],
            )
        except ToolRegistryError as exc:
            self._refused[module_id] = fingerprint
            logger.error(f"Remote tools: module '{module_id}' not published: {exc}")
            return False
        self._published[module_id] = fingerprint
        self._refused.pop(module_id, None)
        logger.info(
            f"Remote tools: module '{module_id}' serves {len(module.definitions)} tool(s)"
        )
        return True

    def start(self) -> None:
        """Read the directory once now, then every ``refresh_seconds`` in the background."""
        if self._thread is not None:
            return
        self._stop.clear()
        self._safe_sync()
        self._thread = threading.Thread(
            target=self._run, name="remote-tool-sync", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(timeout=self._refresh + 15)

    def _run(self) -> None:
        while not self._stop.wait(self._refresh):
            self._safe_sync()

    def _safe_sync(self) -> None:
        try:
            self.sync_once()
        except Exception:  # noqa: BLE001 - the loop must outlive one bad read
            logger.opt(exception=True).error("Remote tools: synchronisation failed")
