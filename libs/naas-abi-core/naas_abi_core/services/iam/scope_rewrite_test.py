"""The plan every store applies when the names are rewritten: twins merge into
the row made first."""

from __future__ import annotations

from datetime import UTC, datetime

from naas_abi_core.services.iam.IAMPorts import (
    ScopedRow,
    ScopeRewrite,
    plan_scope_rewrite,
)

NEW = {"abi:o:-": "org", "abi:o:*": "org/*", "abi:_none:w": "ws", "abi:o:w": "ws"}


def rewrite(scope: str | None) -> str | None:
    return NEW.get(scope or "", scope)


def at(hour: int) -> datetime:
    return datetime(2026, 11, 16, hour, tzinfo=UTC)


def test_rows_with_no_twin_are_rewritten_or_kept():
    plan = plan_scope_rewrite(
        [
            ScopedRow("a", ("p", "u"), "abi:o:-", at(1)),
            ScopedRow("b", ("p", "u"), "org/*", at(1)),
            ScopedRow("c", ("p", "u"), None, at(1)),
        ],
        rewrite,
    )
    assert plan == ScopeRewrite({"a": "org"}, {})


def test_the_twin_made_first_is_kept():
    # The old row came first: it is rewritten, the new one goes.
    assert plan_scope_rewrite(
        [
            ScopedRow("old", ("p", "u"), "abi:o:-", at(1)),
            ScopedRow("new", ("p", "u"), "org", at(2)),
        ],
        rewrite,
    ) == ScopeRewrite({"old": "org"}, {"new": "old"})
    # The new row came first: it stays as it is, the old one goes.
    assert plan_scope_rewrite(
        [
            ScopedRow("old", ("p", "u"), "abi:o:-", at(3)),
            ScopedRow("new", ("p", "u"), "org", at(2)),
        ],
        rewrite,
    ) == ScopeRewrite({}, {"old": "new"})


def test_on_the_same_date_the_old_grammar_wins_and_naive_dates_are_utc():
    naive = datetime(2026, 11, 16, 1)
    assert plan_scope_rewrite(
        [
            ScopedRow("new", ("p", "u"), "org", at(1)),
            ScopedRow("old", ("p", "u"), "abi:o:-", naive),
        ],
        rewrite,
    ) == ScopeRewrite({"old": "org"}, {"new": "old"})


def test_two_old_names_of_one_container_merge_too():
    plan = plan_scope_rewrite(
        [
            ScopedRow("orgless", ("p", "u"), "abi:_none:w", None),
            ScopedRow("in-org", ("p", "u"), "abi:o:w", at(1)),
            ScopedRow("other", ("p", "v"), "abi:o:w", at(1)),
        ],
        rewrite,
    )
    # No date reads as made first.
    assert plan == ScopeRewrite({"orgless": "ws", "other": "ws"}, {"in-org": "orgless"})
