"""Versionstore benchmark.

Measures writes/sec across a small matrix of configurations:

  - Concurrency: 1, 4, 16, 64 writers
  - Workload shape:
      * disjoint   - each writer owns its own uid
      * same-uid   - all writers contend for one uid (serialized by the
                     in-process per-(branch, uid) lock)
      * branched   - half write main, half write feature-x (same uid)
  - Commit mode: solo (commit_window_ms=0) and group commit at various windows

The numbers are not "TPC-C". They are:

  - bound by ``fsync`` on whatever filesystem `tmp` lives on,
  - dependent on Python GIL, scheduler, and SQLite's WAL fsync cadence,
  - run in-process and so understate cross-process contention,
  - run on a temp dir that may be on a different FS class than production.

Their value is comparative: solo vs group commit, low vs high concurrency,
disjoint vs contended workloads. Treat them as direction, not as SLOs.

Run::

    uv run python -m naas_abi_core.utils.versionstore.benchmark
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from .store import Store


# --------------------------------------------------------------------- types


@dataclass
class Result:
    label: str
    workers: int
    workload: str
    commit_window_ms: float
    durability: str
    payload_bytes: int
    n_writes: int
    elapsed_s: float
    batch_count: int
    batched_writes: int

    @property
    def writes_per_sec(self) -> float:
        return self.n_writes / self.elapsed_s if self.elapsed_s > 0 else 0.0

    @property
    def latency_ms(self) -> float:
        # Wall-clock-per-write with ``workers`` concurrency. With perfect
        # scaling this is ``elapsed_s * workers / n_writes * 1000``; with
        # zero scaling it's ``elapsed_s / n_writes * 1000``. We report the
        # former (per-writer-thread latency) which is more meaningful.
        if self.n_writes == 0:
            return 0.0
        return self.elapsed_s * self.workers / self.n_writes * 1000.0

    @property
    def amortization(self) -> float:
        if self.batch_count == 0:
            return 0.0
        return self.batched_writes / self.batch_count


# ------------------------------------------------------------------ workloads


def workload_disjoint(
    store: Store, workers: int, writes_per_worker: int, payload_bytes: int
) -> int:
    """Each worker writes a sequence of payloads under its own uid."""
    payload = b"x" * payload_bytes

    def run(i: int) -> int:
        n = 0
        for j in range(writes_per_worker):
            # Append a unique discriminator so successive payloads differ.
            r = store.put(f"uid-{i}", payload + j.to_bytes(8, "little"))
            if r is not None:
                n += 1
        return n

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run, i) for i in range(workers)]
        return sum(f.result() for f in as_completed(futures))


def workload_same_uid(
    store: Store, workers: int, writes_per_worker: int, payload_bytes: int
) -> int:
    """All workers contend for one uid. The per-(branch, uid) in-process
    lock serializes them; group commit can't help here because writes are
    sequential by construction."""
    payload = b"x" * payload_bytes

    def run(i: int) -> int:
        n = 0
        for j in range(writes_per_worker):
            # Each call must produce a fresh content_hash; encode (worker, j).
            tag = (i.to_bytes(4, "little") + j.to_bytes(8, "little"))
            r = store.put("contended", payload + tag)
            if r is not None:
                n += 1
        return n

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run, i) for i in range(workers)]
        return sum(f.result() for f in as_completed(futures))


def workload_branched(
    store: Store, workers: int, writes_per_worker: int, payload_bytes: int
) -> int:
    """Half the workers write to main, half write to feature-x, all on the
    same uid. The per-(branch, uid) lock keeps within-branch writes
    serialized but allows the two branches to run in parallel."""
    payload = b"x" * payload_bytes
    if "feature-x" not in store.list_branches():
        store.create_branch("feature-x")

    def run(i: int) -> int:
        branch = "main" if i % 2 == 0 else "feature-x"
        n = 0
        for j in range(writes_per_worker):
            tag = i.to_bytes(4, "little") + j.to_bytes(8, "little")
            r = store.put("contended", payload + tag, branch=branch)
            if r is not None:
                n += 1
        return n

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run, i) for i in range(workers)]
        return sum(f.result() for f in as_completed(futures))


WORKLOADS = {
    "disjoint": workload_disjoint,
    "same-uid": workload_same_uid,
    "branched": workload_branched,
}


# --------------------------------------------------------------------- runner


def run_one(
    *,
    label: str,
    root: Path,
    workload: str,
    workers: int,
    writes_per_worker: int,
    payload_bytes: int,
    commit_window_ms: float,
    commit_max_size: int,
    durability: str,
) -> Result:
    fn = WORKLOADS[workload]
    with Store(
        root,
        durability=durability,
        commit_window_ms=commit_window_ms,
        commit_max_size=commit_max_size,
    ) as store:
        # Touch the FS first so dir creation isn't on the hot path.
        store.put("warmup", b"")
        t0 = time.perf_counter()
        n = fn(store, workers, writes_per_worker, payload_bytes)
        t1 = time.perf_counter()
        return Result(
            label=label,
            workers=workers,
            workload=workload,
            commit_window_ms=commit_window_ms,
            durability=durability,
            payload_bytes=payload_bytes,
            n_writes=n,
            elapsed_s=t1 - t0,
            batch_count=store._batch_count,
            batched_writes=store._batched_writes,
        )


def fmt_table(results: list[Result]) -> str:
    headers = [
        "workload",
        "workers",
        "durability",
        "commit",
        "writes",
        "elapsed",
        "writes/s",
        "lat/ms",
        "batches",
        "batched",
        "amort",
    ]
    rows = []
    for r in results:
        if r.commit_window_ms == 0.0:
            commit = "solo"
        else:
            commit = f"{r.commit_window_ms:g}ms"
        rows.append(
            [
                r.workload,
                str(r.workers),
                r.durability,
                commit,
                str(r.n_writes),
                f"{r.elapsed_s:.2f}s",
                f"{r.writes_per_sec:>8,.0f}",
                f"{r.latency_ms:>6.2f}",
                str(r.batch_count) if r.batch_count else "-",
                str(r.batched_writes) if r.batched_writes else "-",
                f"{r.amortization:.1f}x" if r.batch_count else "-",
            ]
        )
    widths = [
        max(len(h), max((len(row[i]) for row in rows), default=0))
        for i, h in enumerate(headers)
    ]

    def fmt_row(row):
        return "  ".join(c.ljust(w) for c, w in zip(row, widths))

    sep = "  ".join("-" * w for w in widths)
    return "\n".join([fmt_row(headers), sep, *(fmt_row(row) for row in rows)])


# ----------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--writes-per-worker", type=int, default=200)
    p.add_argument("--payload-bytes", type=int, default=256)
    p.add_argument("--max-size", type=int, default=64)
    p.add_argument(
        "--workers",
        type=int,
        nargs="+",
        default=[1, 4, 16, 64],
        help="concurrency levels to sweep",
    )
    p.add_argument(
        "--windows",
        type=float,
        nargs="+",
        default=[0.0, 1.0, 2.0, 5.0, 10.0],
        help="commit_window_ms values to sweep (0 = solo)",
    )
    p.add_argument(
        "--workloads",
        nargs="+",
        default=list(WORKLOADS.keys()),
        choices=list(WORKLOADS.keys()),
    )
    p.add_argument(
        "--durabilities",
        nargs="+",
        default=["full", "fast"],
        choices=["full", "fast"],
        help="durability modes to sweep",
    )
    args = p.parse_args(argv)

    print(
        f"\nversionstore benchmark — "
        f"writes/worker={args.writes_per_worker}, "
        f"payload={args.payload_bytes}B, "
        f"max_size={args.max_size}\n"
    )
    print(f"  python      : {sys.version.split()[0]}")
    print(f"  platform    : {sys.platform}")
    print(f"  cpu_count   : {os.cpu_count()}")
    print()

    results: list[Result] = []
    for durability in args.durabilities:
        for workload in args.workloads:
            for workers in args.workers:
                for window_ms in args.windows:
                    # same-uid is serialized; group commit can't help. Keep
                    # the table compact by only running solo and one window.
                    if workload == "same-uid" and window_ms not in (0.0, 5.0):
                        continue
                    with tempfile.TemporaryDirectory(prefix="vs-bench-") as tmp:
                        r = run_one(
                            label=f"{durability}/{workload}/{workers}/{window_ms}ms",
                            root=Path(tmp),
                            workload=workload,
                            workers=workers,
                            writes_per_worker=args.writes_per_worker,
                            payload_bytes=args.payload_bytes,
                            commit_window_ms=window_ms,
                            commit_max_size=args.max_size,
                            durability=durability,
                        )
                        results.append(r)
                        print(
                            f"  done: {r.label:<40}  "
                            f"{r.writes_per_sec:>8,.0f} writes/s  "
                            f"({r.elapsed_s:>5.2f}s)"
                        )

    print("\n" + fmt_table(results) + "\n")

    # Highlight the headline numbers.
    by_key = {
        (r.durability, r.workload, r.workers, r.commit_window_ms): r
        for r in results
    }

    def find(durability: str, workload: str, workers: int, window: float):
        return by_key.get((durability, workload, workers, window))

    print("Headline comparisons (writes/s):\n")
    for durability in args.durabilities:
        print(f"  durability={durability!r}:")
        for workload in ["disjoint", "branched"]:
            for workers in args.workers:
                solo = find(durability, workload, workers, 0.0)
                best_group = max(
                    (
                        find(durability, workload, workers, w)
                        for w in args.windows
                        if w > 0
                    ),
                    key=lambda r: r.writes_per_sec if r else 0,
                    default=None,
                )
                if solo is None or best_group is None:
                    continue
                ratio = best_group.writes_per_sec / max(solo.writes_per_sec, 1)
                print(
                    f"    {workload:<10} workers={workers:>3}  "
                    f"solo={solo.writes_per_sec:>8,.0f}  "
                    f"best-group={best_group.writes_per_sec:>8,.0f}  "
                    f"({best_group.commit_window_ms:g}ms, {ratio:.2f}x)"
                )
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
