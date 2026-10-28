"""Ontologies a module sends to the engine's schema graph (decision in core's
``services/triple_store/AGENTS.md``).

A module ships its ontologies as ``.ttl`` files in an ``ontologies/`` folder next to its
package, as in-engine modules do. Once the instance serves, ``run_module`` sends each file to
the triple store (``load_schema``) as ``module/<module_id>/<path relative to ontologies/>``,
the key the engine stores it under. The engine accepts a module's files only under its own id.

Loading is additive, as for in-engine modules: a file removed later stays in the schema graph.
A failed load never changes readiness: it is logged as an error. A transient failure (the
engine unreachable or busy) is retried in the background; a refusal that cannot change
(``INVALID_ARGUMENT``: not Turtle, a forged ``internal:`` vocabulary, a malformed source;
``PERMISSION_DENIED``) is logged once, and that file is not sent again by this process.
"""

from __future__ import annotations

import asyncio
import logging
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from naas_abi_sdk.services import TripleStoreService

logger = logging.getLogger(__name__)

# The engine refuses a longer source (triple_store primary adapter: MAX_SCHEMA_SOURCE_LENGTH).
MAX_SOURCE_LENGTH = 512
SOURCE_PREFIX = "module"
_MODULE_ID = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.:-]{0,255}")
_SEGMENT = re.compile(r"[A-Za-z0-9_.-]+")
# What the engine answers to a file that no retry makes acceptable. NOT_FOUND:
# the module may load no schema at all (triple_store:LoadSchema), so it cannot
# even see the source; like a refusal, only an approved manifest changes it.
TERMINAL_CODES = frozenset({"INVALID_ARGUMENT", "PERMISSION_DENIED", "NOT_FOUND"})
# Seconds between attempts at a failed load: doubled each time, up to the cap.
RETRY_FIRST_SECONDS = 1.0
RETRY_MAX_SECONDS = 60.0


def schema_source(module_id: str, name: str) -> str:
    """The key ``name`` (a path relative to ``ontologies/``, with ``/``) is stored under.

    Raises ``ValueError`` for a name the engine would refuse: it must end in ``.ttl``, with
    segments of letters, digits, ``_``, ``.`` and ``-`` (never ``.`` or ``..``), and the
    whole source stays within :data:`MAX_SOURCE_LENGTH` characters.
    """
    if not _MODULE_ID.fullmatch(module_id):
        raise ValueError(f"Not a module id: {module_id!r}")
    segments = name.split("/")
    if (
        not name.endswith(".ttl")
        or any(not _SEGMENT.fullmatch(segment) for segment in segments)
        or any(segment in (".", "..") for segment in segments)
    ):
        raise ValueError(
            f"Ontology {name!r}: a relative path of .ttl file names made of letters, "
            "digits, '_', '.' and '-'"
        )
    source = f"{SOURCE_PREFIX}/{module_id}/{name}"
    if len(source) > MAX_SOURCE_LENGTH:
        raise ValueError(
            f"Ontology {name!r}: its source {source!r} is longer than "
            f"{MAX_SOURCE_LENGTH} characters"
        )
    return source


@dataclass(frozen=True)
class OntologyFile:
    path: Path
    # Relative to the module's ontologies/ folder, always with "/".
    name: str

    def source(self, module_id: str) -> str:
        return schema_source(module_id, self.name)


def module_ontologies_dir(module_type: type) -> Path | None:
    """``ontologies/`` next to the module's package (its ``__init__.py``)."""
    module = sys.modules.get(module_type.__module__)
    file = getattr(module, "__file__", None)
    if not file:
        return None
    folder = Path(file).resolve().parent / "ontologies"
    return folder if folder.is_dir() else None


def _is_sandbox(name: str) -> bool:
    # As in-engine modules: a path with "sandbox" in it holds work in progress. Only the
    # part under ontologies/ counts, so the folder the package is installed in cannot.
    return "sandbox" in name.lower()


def discover_ontologies(module_type: type) -> tuple[OntologyFile, ...]:
    """Every ``ontologies/**/*.ttl`` of the module except those under ``sandbox``, sorted."""
    folder = module_ontologies_dir(module_type)
    if folder is None:
        return ()
    files = []
    for path in sorted(folder.rglob("*.ttl")):
        name = path.relative_to(folder).as_posix()
        if path.is_file() and not _is_sandbox(name):
            files.append(OntologyFile(path, name))
    return tuple(files)


def declared_ontologies(
    module_type: type, declared: tuple[str | Path, ...]
) -> tuple[OntologyFile, ...]:
    """The ``.ttl`` files a module names (paths relative to its ``ontologies/`` folder)."""
    folder = module_ontologies_dir(module_type)
    files = []
    for entry in declared:
        name = Path(entry).as_posix()
        if folder is None or not (folder / name).is_file():
            raise ValueError(
                f"Ontology {name!r} is not a file of the module's ontologies/ folder"
            )
        files.append(OntologyFile((folder / name).resolve(), name))
    return tuple(files)


class OntologyLoader:
    """Sends a module's ontologies to the schema graph, retrying transient failures
    until all load.

    ``serving`` says whether the instance may send (``READY`` or ``DEGRADED``, never while
    ``STAGED``) and ``stopping`` whether it was asked to drain. A file is read again for
    every attempt. Nothing here raises for a failed load: it is logged and retried, after
    1 s and then twice as long each time, up to a minute.
    """

    def __init__(
        self,
        triple_store: TripleStoreService,
        module_id: str,
        files: tuple[OntologyFile, ...],
        *,
        serving: Callable[[], bool] = lambda: True,
        stopping: Callable[[], bool] = lambda: False,
        poll_seconds: float = 2.0,
        retry_first_seconds: float = RETRY_FIRST_SECONDS,
        retry_max_seconds: float = RETRY_MAX_SECONDS,
    ) -> None:
        # Fail before the module serves, not in a background task.
        self._sources = {f.name: f.source(module_id) for f in files}
        self._triple_store = triple_store
        self._files = files
        self._serving, self._stopping = serving, stopping
        self._poll = poll_seconds
        self._retry_first, self._retry_max = retry_first_seconds, retry_max_seconds
        self.pending: dict[str, OntologyFile] = {f.name: f for f in files}
        self.refused: dict[str, str] = {}

    async def run(self) -> None:
        """Return when every file is loaded, or the module is asked to drain."""
        while not self._serving():
            if self._stopping():
                return
            await asyncio.sleep(self._poll)
        delay = self._retry_first
        while self.pending:
            for name, file in list(self.pending.items()):
                if self._stopping():
                    return
                outcome = await self._load(file)
                if outcome is not None:
                    del self.pending[name]
                    if outcome is False:
                        self.refused[name] = self._sources[name]
            if self.pending:
                await asyncio.sleep(delay)
                delay = min(delay * 2, self._retry_max)

    async def _load(self, file: OntologyFile) -> bool | None:
        """True: loaded. False: refused for good. None: failed, to retry."""
        source = self._sources[file.name]
        try:
            content = await asyncio.to_thread(file.path.read_bytes)
            changed = await self._triple_store.load_schema(source, content)
        except Exception as exc:  # noqa: BLE001 - never ends the module
            if getattr(exc, "code", None) in TERMINAL_CODES:
                logger.error(
                    "The engine refused ontology %s (%s), so it is not loaded and "
                    "not sent again until the module restarts: fix %s. %s",
                    source,
                    exc.code,  # type: ignore[attr-defined]
                    file.path,
                    exc,
                )
                return False
            logger.error(
                "Could not load ontology %s into the schema graph (will retry): %s",
                source,
                exc,
            )
            return None
        logger.info(
            "Ontology %s %s", source, "loaded" if changed else "already up to date"
        )
        return True


def module_ontology_files(module_type: Any, module_id: str) -> tuple[OntologyFile, ...]:
    """The ontologies of a module, checked: what ``run_module`` will send.

    Raises ``ValueError`` for a file name the engine would refuse, and for a module
    with ontologies that does not declare the ``triple_store`` service.
    """
    files = module_type.get_ontologies()
    for file in files:
        file.source(module_id)
    if files and "triple_store" not in module_type.get_dependencies().services:
        raise ValueError(
            f"Module {module_id!r} has ontologies ({', '.join(f.name for f in files)}) "
            "but does not declare the triple_store service: add "
            "ModuleDependencies(services=('triple_store',)) to its dependencies"
        )
    return files
