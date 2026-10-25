"""Listing and age-filtering of the persisted search envelopes.

Shared by the Dagster files-reprocess orchestration and the durable
``reprocess_tweet_envelopes`` flow; imports no Dagster.
"""

from __future__ import annotations

import posixpath
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from naas_abi_core import logger

ENVELOPE_EXTENSIONS = (".json", ".ndjson", ".json.gz", ".ndjson.gz")
# ``2026-07-23T15:46:04.705264+00:00_<slug>.json`` or underscored older form
# ``2026-06-29T17_58_45.974146+00_00_<slug>.json``.
ENVELOPE_TS_RE = re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2}T[\d_:.+-]+?)_")
_LIST_ENVELOPE_PROGRESS_INTERVAL_S = 30.0


def reprocess_log(
    log: Callable[[str], None] | None,
    *,
    config_name: str,
    run_id: str,
    phase: str,
    message: str,
) -> None:
    """Emit to Dagster step logs (stderr) and the shared application logger."""
    line = (
        f"XSearchRecentTweetsFilesOrchestration[{config_name}] "
        f"run_id={run_id} phase={phase}: {message}"
    )
    if log is not None:
        log(line)
    logger.info(line)


@dataclass
class ListEnvelopeProgress:
    """Counters for long recursive object-storage listing sweeps."""

    log: Callable[[str], None] | None
    config_name: str
    run_id: str
    started_at: float = field(default_factory=time.monotonic)
    last_logged_at: float = field(default_factory=time.monotonic)
    list_calls: int = 0
    keys_seen: int = 0
    envelopes_kept: int = 0
    skipped_age: int = 0
    prefixes_visited: int = 0

    def note_list_call(self) -> None:
        self.list_calls += 1

    def note_prefix_visited(self) -> None:
        self.prefixes_visited += 1

    def note_key(self) -> None:
        self.keys_seen += 1

    def note_envelope_kept(self) -> None:
        self.envelopes_kept += 1

    def note_skipped_age(self) -> None:
        self.skipped_age += 1

    def maybe_log_progress(self, *, force: bool = False) -> None:
        now = time.monotonic()
        if (
            not force
            and (now - self.last_logged_at) < _LIST_ENVELOPE_PROGRESS_INTERVAL_S
        ):
            if self.keys_seen == 0 or self.keys_seen % 500 != 0:
                return
        self.last_logged_at = now
        elapsed = now - self.started_at
        reprocess_log(
            self.log,
            config_name=self.config_name,
            run_id=self.run_id,
            phase="list_envelopes",
            message=(
                f"progress elapsed={elapsed:.1f}s list_calls={self.list_calls} "
                f"prefixes_visited={self.prefixes_visited} keys_seen={self.keys_seen} "
                f"envelopes_kept={self.envelopes_kept} skipped_age={self.skipped_age}"
            ),
        )


def envelope_path_timestamp(file_path: str) -> datetime | None:
    """Parse the leading ISO (or underscored-ISO) timestamp from an envelope key.

    Returns an aware UTC datetime, or ``None`` when the basename does not match
    the ``<ts>_<slug>.json`` convention.
    """
    name = posixpath.basename(file_path)
    match = ENVELOPE_TS_RE.match(name)
    if not match:
        return None
    stamp = match.group("ts")
    # Older files used underscores in the time / offset: ``T17_58_45…+00_00``.
    if "+00_00" in stamp or (stamp.count("_") >= 2 and "T" in stamp):
        try:
            date, rest = stamp.split("T", 1)
            if "+" not in rest:
                return None
            time_part, tz = rest.rsplit("+", 1)
            parsed = datetime.fromisoformat(
                f"{date}T{time_part.replace('_', ':')}+{tz.replace('_', ':')}"
            )
        except ValueError:
            return None
    else:
        try:
            parsed = datetime.fromisoformat(stamp)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def within_max_age(file_path: str, cutoff: datetime) -> bool:
    """True iff *file_path*'s filename timestamp is parseable and ``>= cutoff``."""
    ts = envelope_path_timestamp(file_path)
    return ts is not None and ts >= cutoff


def path_is_envelope(file_path: str) -> bool:
    return file_path.lower().endswith(ENVELOPE_EXTENSIONS)


def full_object_path(prefix: str, key: str) -> str:
    prefix = prefix.rstrip("/")
    if key.startswith(prefix):
        return key
    return posixpath.join(prefix, key)


def filter_dir_envelopes_by_cutoff(
    envelope_paths: list[str],
    cutoff: datetime,
    *,
    progress: ListEnvelopeProgress | None = None,
) -> tuple[list[str], int]:
    """Keep in-window envelopes; stop after the newest contiguous in-window run."""
    if not envelope_paths:
        return [], 0
    sortable: list[tuple[datetime | None, str]] = [
        (envelope_path_timestamp(path), path) for path in envelope_paths
    ]

    def _sort_key(item: tuple[datetime | None, str]) -> tuple[int, datetime]:
        ts, _ = item
        if ts is None:
            return (0, datetime.min.replace(tzinfo=UTC))
        return (1, ts)

    sortable.sort(key=_sort_key, reverse=True)
    kept: list[str] = []
    for ts, path in sortable:
        if ts is None or ts < cutoff:
            break
        kept.append(path)
        if progress is not None:
            progress.note_envelope_kept()
    skipped = len(envelope_paths) - len(kept)
    if progress is not None and skipped:
        for _ in range(skipped):
            progress.note_skipped_age()
    return kept, skipped


def list_envelopes_in_prefix_dir(
    object_storage,
    prefix: str,
    *,
    cutoff: datetime,
    progress: ListEnvelopeProgress | None = None,
) -> tuple[list[str], int]:
    """List envelope files under one prefix directory, bounded by *cutoff*."""
    prefix = prefix.rstrip("/")
    try:
        if progress is not None:
            progress.note_list_call()
        keys = object_storage.list_objects(prefix) or []
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            f"XSearchRecentTweetsFilesOrchestration: list_objects({prefix!r}) "
            f"failed ({exc})"
        )
        return [], 0
    if progress is not None:
        progress.note_prefix_visited()
        for _ in keys:
            progress.note_key()

    local_envelopes: list[str] = []
    paths: list[str] = []
    skipped_age = 0
    for key in keys:
        if not key:
            continue
        full_path = full_object_path(prefix, key)
        base = posixpath.basename(full_path.rstrip("/"))
        if base == ".nexus_folder":
            continue
        if full_path.endswith("/") or not path_is_envelope(full_path):
            child_paths, child_skipped = list_envelopes_in_prefix_dir(
                object_storage,
                full_path.rstrip("/"),
                cutoff=cutoff,
                progress=progress,
            )
            paths.extend(child_paths)
            skipped_age += child_skipped
            continue
        local_envelopes.append(full_path)

    kept, skipped = filter_dir_envelopes_by_cutoff(
        local_envelopes, cutoff, progress=progress
    )
    paths.extend(kept)
    return paths, skipped_age + skipped


def list_envelope_paths_within_cutoff(
    object_storage,
    prefix: str,
    *,
    cutoff: datetime,
    progress: ListEnvelopeProgress | None = None,
) -> tuple[list[str], int]:
    """Two-level slug/file listing with per-directory age cutoffs."""
    prefix = prefix.rstrip("/")
    try:
        if progress is not None:
            progress.note_list_call()
        top_keys = object_storage.list_objects(prefix) or []
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            f"XSearchRecentTweetsFilesOrchestration: list_objects({prefix!r}) "
            f"failed ({exc})"
        )
        return [], 0
    if progress is not None:
        progress.note_prefix_visited()
        for _ in top_keys:
            progress.note_key()

    paths: list[str] = []
    skipped_age = 0
    for key in top_keys:
        if not key:
            continue
        full_path = full_object_path(prefix, key)
        base = posixpath.basename(full_path.rstrip("/"))
        if base == ".nexus_folder":
            continue
        if full_path.endswith("/") or not path_is_envelope(full_path):
            child_prefix = full_path.rstrip("/")
            child_paths, child_skipped = list_envelopes_in_prefix_dir(
                object_storage,
                child_prefix,
                cutoff=cutoff,
                progress=progress,
            )
            paths.extend(child_paths)
            skipped_age += child_skipped
            continue
        kept, skipped = filter_dir_envelopes_by_cutoff(
            [full_path], cutoff, progress=progress
        )
        paths.extend(kept)
        skipped_age += skipped
    return paths, skipped_age


def list_envelope_paths(
    object_storage,
    prefix: str,
    *,
    cutoff: datetime | None = None,
    _seen: set[str] | None = None,
    progress: ListEnvelopeProgress | None = None,
) -> tuple[list[str], int]:
    """Full object-storage paths of every envelope file under *prefix*.

    ``list_objects`` is depth-1 only (direct children). Envelopes live under
    ``<prefix>/<slug>/<ts>_<slug>.json``, so this walks into subdirectory
    children (S3 common-prefixes ending in ``/``, or FS directory names)
    until it finds JSON envelope files. Returned paths are the full
    ``prefix/…/file`` keys the pipeline's ``file_path`` mode expects.

    When *cutoff* is set, each envelope key is age-checked from its filename
    timestamp **while listing** (older / unparseable keys are dropped and
    counted in the returned skip total). Callers that set *cutoff* should still
    run :func:`filter_paths_by_max_age` as a second filename pass.
    """
    prefix = prefix.rstrip("/")
    if cutoff is not None:
        return list_envelope_paths_within_cutoff(
            object_storage, prefix, cutoff=cutoff, progress=progress
        )
    seen = _seen if _seen is not None else set()
    if not prefix or prefix in seen:
        return [], 0
    seen.add(prefix)
    if progress is not None:
        progress.note_prefix_visited()

    try:
        if progress is not None:
            progress.note_list_call()
        all_keys = object_storage.list_objects(prefix) or []
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            f"XSearchRecentTweetsFilesOrchestration: list_objects({prefix!r}) "
            f"failed ({exc})"
        )
        return [], 0

    paths: list[str] = []
    skipped_age = 0
    for k in all_keys:
        if not k:
            continue
        if progress is not None:
            progress.note_key()
            progress.maybe_log_progress()
        full_path = k if k.startswith(prefix) else posixpath.join(prefix, k)
        base = posixpath.basename(full_path.rstrip("/"))
        # Nexus folder markers are zero-byte placeholders, not real prefixes.
        if base == ".nexus_folder":
            continue
        if full_path.endswith("/"):
            child_paths, child_skipped = list_envelope_paths(
                object_storage,
                full_path.rstrip("/"),
                cutoff=cutoff,
                _seen=seen,
                progress=progress,
            )
            paths.extend(child_paths)
            skipped_age += child_skipped
            continue
        if full_path.lower().endswith(ENVELOPE_EXTENSIONS):
            if cutoff is not None and not within_max_age(full_path, cutoff):
                skipped_age += 1
                if progress is not None:
                    progress.note_skipped_age()
                continue
            paths.append(full_path)
            if progress is not None:
                progress.note_envelope_kept()
            continue
        # Non-envelope child with no trailing slash — likely a slug dir (FS
        # adapter) or an unrelated file. Recurse; empty/missing dirs no-op.
        child_paths, child_skipped = list_envelope_paths(
            object_storage,
            full_path,
            cutoff=cutoff,
            _seen=seen,
            progress=progress,
        )
        paths.extend(child_paths)
        skipped_age += child_skipped
    return paths, skipped_age


def filter_paths_by_max_age(
    paths: list[str],
    *,
    cutoff: datetime,
) -> tuple[list[str], int]:
    """Second-pass filename age filter (same rule as listing-time check).

    Paths with unparseable timestamps or ``ts < cutoff`` are dropped. Kept even
    after listing already filtered, as a safety net against key-shape edge cases.
    """
    kept: list[str] = []
    skipped = 0
    for path in paths:
        if not within_max_age(path, cutoff):
            skipped += 1
            continue
        kept.append(path)
    return kept, skipped


def mapped_file_paths(triple_store, graph_name: str, namespace: str) -> set[str]:
    """Every ``x:file_path`` already recorded on an ``x:SearchResultSet``.

    A SPARQL SELECT against the configured named graph for the file paths of
    the result sets already mapped — the set of envelopes we can skip on a
    reprocess run. The ``x:file_path`` the pipeline stores is exactly the
    ``prefix/key`` path produced by :func:`list_envelope_paths`, so the
    returned strings are directly comparable.
    """
    class_uri = f"{namespace}SearchResultSet"
    prop_uri = f"{namespace}file_path"
    sparql = (
        f"SELECT DISTINCT ?fp WHERE {{ GRAPH <{graph_name}> {{ "
        f"?s a <{class_uri}> ; <{prop_uri}> ?fp . }} }}"
    )
    try:
        result = triple_store.query(sparql)
    except Exception as exc:  # noqa: BLE001
        # Fail open: if the graph can't be queried, fall back to reprocessing
        # everything (the pipeline's label-based dedupe still no-ops re-runs)
        # rather than silently skipping files we couldn't confirm are mapped.
        logger.warning(
            f"XSearchRecentTweetsFilesOrchestration: SearchResultSet file_path "
            f"query failed ({exc}); treating all files as not-yet-mapped"
        )
        return set()
    return {str(row.fp) for row in result if getattr(row, "fp", None) is not None}
