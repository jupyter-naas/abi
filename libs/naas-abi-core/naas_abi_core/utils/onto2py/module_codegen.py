"""
Run onto2py over one module's ontologies, skipping files that have not changed.

Order, per module:

1. ``ontologies/processes/*.ttl``: onto2py on every process slice.
2. Consolidate the slices into ``ontologies/modules/<Module>Ontology.ttl``
   (see :mod:`naas_abi_core.utils.onto2py.consolidate`).
3. ``ontologies/modules/*.ttl`` that declare ``a owl:Ontology``: onto2py.

Each TTL's sha256 is stored in ``ontologies/onto2py.lock.json`` once its
Python is generated. A file whose hash matches and whose ``.py`` exists is
skipped before onto2py runs, so an unchanged module costs no ontology check,
no ``owl:imports`` resolution and no rdflib parse.

The hash covers the TTL's own content and the generator version, not the
ontologies it imports: a change upstream needs ``force=True``. Process changes
do reach the module ontology, because consolidation rewrites its content.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from naas_abi_core.utils.onto2py.consolidate import consolidate_processes
from naas_abi_core.utils.onto2py.onto2py import _CACHE_KEY_VERSION, onto2py

LOCK_FILE = "onto2py.lock.json"
_ONTOLOGY_DECL_RE = re.compile(r"\ba\s+owl:Ontology\b|owl#Ontology>")


@dataclass
class ModuleCodegenReport:
    module_root: Path
    generated: list[Path] = field(default_factory=list)
    skipped: list[Path] = field(default_factory=list)
    errors: dict[Path, str] = field(default_factory=dict)
    consolidated: Path | None = None

    @property
    def ok(self) -> bool:
        return not self.errors


def file_hash(path: Path) -> str:
    hasher = hashlib.sha256()
    hasher.update(path.read_bytes())
    hasher.update(b"\x00")
    hasher.update(_CACHE_KEY_VERSION.encode("utf-8"))
    return hasher.hexdigest()


def _load_lock(lock_path: Path) -> dict[str, str]:
    try:
        data = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    files = data.get("files") if isinstance(data, dict) else None
    return dict(files) if isinstance(files, dict) else {}


def _save_lock(lock_path: Path, files: dict[str, str]) -> None:
    payload = {"files": dict(sorted(files.items()))}
    text = json.dumps(payload, indent=2) + "\n"
    if not lock_path.exists() or lock_path.read_text(encoding="utf-8") != text:
        lock_path.write_text(text, encoding="utf-8")


def declares_ontology(path: Path) -> bool:
    return bool(_ONTOLOGY_DECL_RE.search(path.read_text(encoding="utf-8")))


def onto2py_module(
    module_root: str | Path,
    force: bool = False,
    generate: Callable[[str], object] = onto2py,
) -> ModuleCodegenReport:
    """Generate Python for one module's process slices and module ontologies.

    ``generate`` is the per-file generator; tests swap it out.
    """
    root = Path(module_root).resolve()
    report = ModuleCodegenReport(module_root=root)
    ontologies = root / "ontologies"
    if not ontologies.is_dir():
        return report

    lock_path = ontologies / LOCK_FILE
    lock = _load_lock(lock_path)

    def run(ttl: Path) -> bool:
        key = ttl.relative_to(ontologies).as_posix()
        digest = file_hash(ttl)
        if not force and lock.get(key) == digest and ttl.with_suffix(".py").exists():
            report.skipped.append(ttl)
            return True
        try:
            generate(str(ttl))
        except Exception as exc:  # noqa: BLE001
            # Leave the old hash in place so the file is retried next run.
            report.errors[ttl] = str(exc)
            return False
        lock[key] = digest
        report.generated.append(ttl)
        return True

    # 1. Process slices.
    processes_ok = True
    for ttl in sorted((ontologies / "processes").glob("*.ttl")):
        processes_ok = run(ttl) and processes_ok

    # 2. Consolidate. Skipped when a slice failed: its statements may not parse.
    if processes_ok:
        try:
            report.consolidated = consolidate_processes(root)
        except Exception as exc:  # noqa: BLE001
            report.errors[ontologies / "processes"] = f"consolidation failed: {exc}"

    # 3. Module ontologies.
    for ttl in sorted((ontologies / "modules").glob("*.ttl")):
        if declares_ontology(ttl):
            run(ttl)

    # Forget files that no longer exist.
    for key in [k for k in lock if not (ontologies / k).exists()]:
        del lock[key]
    _save_lock(lock_path, lock)
    return report
