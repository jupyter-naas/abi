"""Repository guard: fail CI if anything under ``naas_abi_core/`` imports
``concurrent.futures.ThreadPoolExecutor`` directly.

Per spec issue #877, the loud-failure policy demands that branch context
propagate to every worker thread. ``concurrent.futures.ThreadPoolExecutor``
does not propagate ``contextvars`` automatically; using it silently drops
the active branch and produces reads against ``main`` from inside what
the caller thought was a ``BranchContext.use("feature-x")`` block.

The fix is to use ``BranchAwareThreadPoolExecutor`` from this package.
This test is the enforcement: it parses every Python file under
``naas_abi_core/`` and fails if any non-allowlisted file imports the
raw class.

Why a pytest test rather than a ruff plugin? A custom ruff rule would
require shipping a separate plugin package; a stdlib-only AST scan
gives us the same coverage with zero added dependencies, runs as part
of every test invocation, and surfaces the violation with a clear
message at the file level. If/when the project adopts a custom ruff
plugin, this test can become a thin wrapper around it (or be retired
in favor of the rule)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


# Files allowed to import the raw class. Keep this list minimal and
# justified — every entry is documented.
ALLOWLIST: frozenset[str] = frozenset(
    {
        # The wrapper itself: ``BranchAwareThreadPoolExecutor`` subclasses
        # ``ThreadPoolExecutor``. This is the one place the raw class
        # MUST be imported.
        "branching/executor.py",
        # The guard test: it imports the raw class to demonstrate the
        # negative case (raw executor does NOT propagate). Allowlisting
        # the test keeps the demo honest without a # noqa pragma.
        "branching/executor_test.py",
        # This file: the allowlist is data, the docstring above
        # references the class by name.
        "branching/no_raw_threadpool_test.py",
        #
        # ----------------------------------------------------------
        # Migration debt — to be cleared across the per-service
        # branching migration issues (#882–#888 and #883/#884/#887).
        # Each entry below pre-dates BranchContext and uses a raw
        # executor for fan-out that is not yet branch-aware. Once the
        # corresponding service migrates onto IVersionedStorePort, its
        # tests / production paths should switch to
        # BranchAwareThreadPoolExecutor and the entry should be
        # removed from this allowlist.
        # ----------------------------------------------------------
        #
        # Production: agent IntentMapper fan-out, branch-unaware
        # (cleanup with #883, agent memory migration).
        "services/agent/beta/IntentMapper.py",
        # Concurrency test suites for services that pre-date
        # BranchContext. Tests use the executor as a generic fan-out
        # tool, not to exercise branch propagation. Migrate alongside
        # each service in its respective issue.
        "services/bus/adapters/secondary/PythonQueueAdapter_test.py",
        "services/cache/adapters/secondary/CacheFSAdapter_test.py",
        "services/keyvalue/adapters/secondary/PythonAdapter_test.py",
        "services/object_storage/adapters/secondary/ObjectStorageSecondaryAdapterFS_test.py",
        "services/triple_store/adaptors/secondary/TripleStoreService__SecondaryAdaptor__Filesystem_concurrency_test.py",
        "services/triple_store/adaptors/secondary/TripleStoreService__SecondaryAdaptor__OxigraphEmbedded_test.py",
        "services/vector_store/adapters/QdrantInMemoryAdapter_test.py",
        # Vendored versionstore: independent library that intentionally
        # has no naas_abi_core.branching dependency. Its concurrency
        # tests and benchmark belong in the upstream versionstore repo
        # and stay raw on purpose.
        "utils/versionstore/benchmark.py",
        "utils/versionstore/store_concurrency_test.py",
        "utils/versionstore/store_group_commit_test.py",
    }
)


def _package_root() -> Path:
    """Return the on-disk path to the ``naas_abi_core`` package, no
    matter how the test is invoked. ``Path(__file__)`` resolves the
    location of this test, which is two parents up from the package
    root (``naas_abi_core/branching/no_raw_threadpool_test.py``)."""
    return Path(__file__).resolve().parent.parent


def _imports_raw_threadpool(source: str) -> bool:
    """Return True if ``source`` imports
    ``concurrent.futures.ThreadPoolExecutor`` in any common form."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        # Malformed Python isn't this test's job to flag; let the
        # syntax-error elsewhere surface it.
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == "concurrent.futures":
                for alias in node.names:
                    if alias.name == "ThreadPoolExecutor":
                        return True
        elif isinstance(node, ast.Import):
            for alias in node.names:
                # ``import concurrent.futures`` followed by usage of
                # ``concurrent.futures.ThreadPoolExecutor`` — heuristic
                # check on the module-qualified name in subsequent
                # ``ast.Attribute`` nodes.
                if alias.name == "concurrent.futures":
                    for sub in ast.walk(tree):
                        if (
                            isinstance(sub, ast.Attribute)
                            and sub.attr == "ThreadPoolExecutor"
                        ):
                            return True
    return False


def test_no_raw_thread_pool_executor_in_naas_abi_core():
    """Walk every .py file under ``naas_abi_core/`` and fail if any
    non-allowlisted file imports the raw ``ThreadPoolExecutor``.

    The error message lists every offender with its package-relative
    path and an explanation of what to use instead, so a developer
    seeing this fail in CI doesn't have to come read this test."""
    root = _package_root()
    offenders: list[str] = []
    for py in root.rglob("*.py"):
        rel = py.relative_to(root).as_posix()
        if rel in ALLOWLIST:
            continue
        try:
            source = py.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if _imports_raw_threadpool(source):
            offenders.append(rel)
    if offenders:
        offenders_block = "\n  ".join(sorted(offenders))
        pytest.fail(
            "These files import concurrent.futures.ThreadPoolExecutor "
            "directly, which silently drops the BranchContext when "
            "submitting work to threads:\n  "
            + offenders_block
            + "\n\nUse BranchAwareThreadPoolExecutor from "
            "naas_abi_core.branching instead. If a file genuinely needs "
            "the raw class (very rare — the wrapper is a pure superset), "
            "add it to the ALLOWLIST in this test with a one-line "
            "justification.",
            pytrace=False,
        )
