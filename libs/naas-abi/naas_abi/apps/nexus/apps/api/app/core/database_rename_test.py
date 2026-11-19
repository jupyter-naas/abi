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


def test_parses_add_column_statements() -> None:
    from naas_abi.apps.nexus.apps.api.app.core.database import parse_add_columns

    assert parse_add_columns(
        "ALTER TABLE messages ADD COLUMN IF NOT EXISTS feedback VARCHAR(16)"
    ) == ("messages", ["feedback"])
    assert parse_add_columns("alter table users add column x TEXT;") == ("users", ["x"])
    assert parse_add_columns(
        "ALTER TABLE workspaces ADD COLUMN logo_url TEXT, ADD COLUMN price NUMERIC(10,2) "
        'DEFAULT 0, ADD COLUMN IF NOT EXISTS "accent" VARCHAR(20)'
    ) == ("workspaces", ["logo_url", "price", "accent"])
    # Anything but ADD COLUMN clauses is run as written.
    assert parse_add_columns("ALTER TABLE t ADD COLUMN a TEXT, DROP COLUMN b") is None
    assert parse_add_columns("ALTER TABLE t ADD CONSTRAINT c UNIQUE (a)") is None
    assert parse_add_columns("ALTER TABLE t RENAME COLUMN a TO b") is None
    assert parse_add_columns("CREATE TABLE t (a TEXT)") is None


def test_an_add_column_is_skipped_once_every_column_exists() -> None:
    from naas_abi.apps.nexus.apps.api.app.core.database import add_columns_already_applied

    assert add_columns_already_applied({"id", "feedback"}, ["feedback"])
    assert not add_columns_already_applied({"id"}, ["feedback"])
    assert not add_columns_already_applied({"id", "a"}, ["a", "b"])
    assert not add_columns_already_applied({"id"}, [])


def test_every_add_column_of_the_migrations_is_understood() -> None:
    """Each migration's ADD COLUMN statement, as the runner splits it, names its
    columns: none would be re-run (and lock its table) on every boot by mistake."""
    from pathlib import Path

    from naas_abi.apps.nexus.apps.api.app.core.database import (
        _adapt_statement_for_dialect,
        parse_add_columns,
    )

    migrations = Path(__file__).parent.parent.parent / "migrations"
    statements: list[str] = []
    for path in sorted(migrations.glob("*.sql")):
        current: list[str] = []
        for line in path.read_text().split("\n"):
            line = line.strip()
            if line.startswith("--") or not line:
                continue
            if "--" in line:
                line = line[: line.index("--")].strip()
            if line:
                current.append(line)
                if line.endswith(";"):
                    statements.append(" ".join(current).rstrip(";"))
                    current = []
    adds = [s for s in statements if " ADD COLUMN " in s.upper().replace("\n", " ")]
    assert any("messages" in s and "feedback" in s for s in adds)
    for statement in adds:
        for dialect in ("postgresql", "sqlite"):
            for adapted in _adapt_statement_for_dialect(statement, dialect):
                parsed = parse_add_columns(adapted)
                assert parsed is not None and parsed[1], adapted
