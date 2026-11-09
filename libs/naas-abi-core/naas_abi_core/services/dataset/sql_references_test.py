"""What a dataset query reads, as its authorization sees it."""

from __future__ import annotations

import pytest
from naas_abi_core.services.dataset.sql_references import referenced_datasets


@pytest.mark.parametrize(
    "sql, expected",
    [
        ("SELECT * FROM orders", [("ns", "orders")]),
        ("SELECT * FROM sales.orders", [("sales", "orders")]),
        # A CTE hides a dataset of its name only where it is in scope.
        (
            (
                "SELECT * FROM secret WHERE EXISTS "
                "(WITH secret AS (SELECT 1) SELECT * FROM secret)"
            ),
            [("ns", "secret")],
        ),
        (
            "WITH a AS (SELECT * FROM orders), b AS (SELECT * FROM a) SELECT * FROM b",
            [("ns", "orders")],
        ),
        (
            (
                "WITH RECURSIVE r AS (SELECT 1 AS n UNION ALL SELECT n + 1 FROM r "
                "WHERE n < 3) SELECT * FROM r"
            ),
            [],
        ),
        (
            (
                "WITH x AS (SELECT * FROM orders) SELECT * FROM x, "
                "(WITH y AS (SELECT 1) SELECT * FROM x) z"
            ),
            [("ns", "orders")],
        ),
        ("SELECT * FROM a UNION ALL SELECT * FROM b", [("ns", "a"), ("ns", "b")]),
        ("SELECT * FROM range(3)", []),
        # A recursive CTE's anchor runs before the CTE exists: a table of its
        # name there is a dataset.
        (
            (
                "WITH RECURSIVE t AS (SELECT * FROM t UNION ALL SELECT * FROM t) "
                "SELECT * FROM t"
            ),
            [("ns", "t")],
        ),
        # A WITH inside a recursive CTE is in scope for its anchor too.
        (
            (
                "WITH RECURSIVE t AS (WITH x AS (SELECT 1 AS n) SELECT n FROM x "
                "UNION ALL SELECT n + 1 FROM t WHERE n < 3) SELECT * FROM t"
            ),
            [],
        ),
        (
            (
                "WITH RECURSIVE t AS (WITH x AS (SELECT * FROM orders) "
                "SELECT * FROM x UNION ALL SELECT * FROM t) SELECT * FROM t"
            ),
            [("ns", "orders")],
        ),
        # A CTE may have any name; only datasets must be identifiers.
        ('WITH "a-b" AS (SELECT 1) SELECT * FROM "a-b"', []),
        ("WITH _x AS (SELECT 1) SELECT * FROM _x", []),
    ],
)
def test_references(sql, expected):
    assert referenced_datasets(sql, "ns") == expected


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM '/etc/passwd'",  # a replacement scan reads the file
        'SELECT * FROM "data.parquet"',
        "SELECT * FROM ns.'x.csv'",
        "SELECT * FROM read_csv('x.csv')",
        "SELECT * FROM lake.ns.orders",
        "SELECT * FROM information_schema.tables",
        "SELECT * FROM __ducklake_metadata_abi_datasets.ducklake_table",
        "SELECT * FROM _hidden",
        'SELECT * FROM "orders\n"',  # "$" alone would accept the newline
        "SHOW TABLES",
        "ATTACH 'x.db'",
        "COPY orders TO 'x.csv'",
        "SELECT 1; SELECT 2",
    ],
)
def test_what_cannot_be_vouched_for_is_refused(sql):
    with pytest.raises(ValueError):
        referenced_datasets(sql, "ns")
