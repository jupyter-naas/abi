from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.core.database import (
    parse_rename_column,
    rename_already_applied,
)


def test_parses_rename_column_statements() -> None:
    assert parse_rename_column("ALTER TABLE users RENAME COLUMN company TO organization") == (
        "users",
        "company",
        "organization",
    )
    assert parse_rename_column('alter table "users" rename column "a" to "b";') == (
        "users",
        "a",
        "b",
    )
    assert parse_rename_column("ALTER TABLE users ADD COLUMN x TEXT") is None


def test_rename_is_skipped_once_applied() -> None:
    assert rename_already_applied({"id", "organization"}, "company", "organization")
    assert not rename_already_applied({"id", "company"}, "company", "organization")
