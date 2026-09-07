from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.services.datasets.datasets__schema import (
    DatasetQueryError,
)
from naas_abi.apps.nexus.apps.api.app.services.datasets.sql_safe import (
    assert_read_only_sql,
    clamp_limit,
    preview_sql,
    wrap_limit,
)


def test_allows_select_and_with() -> None:
    assert assert_read_only_sql("SELECT * FROM time_entries") == "SELECT * FROM time_entries"
    assert assert_read_only_sql(
        "WITH x AS (SELECT 1 AS n) SELECT n FROM x"
    ).startswith("WITH")


def test_strips_trailing_semicolon() -> None:
    assert assert_read_only_sql("SELECT 1;") == "SELECT 1"


def test_rejects_empty_and_comments_only() -> None:
    with pytest.raises(DatasetQueryError):
        assert_read_only_sql("   ")
    with pytest.raises(DatasetQueryError):
        assert_read_only_sql("-- just a comment")


def test_rejects_non_select() -> None:
    with pytest.raises(DatasetQueryError, match="only SELECT"):
        assert_read_only_sql("DROP TABLE time_entries")
    with pytest.raises(DatasetQueryError, match="only SELECT"):
        assert_read_only_sql("PRAGMA show_tables")
    with pytest.raises(DatasetQueryError, match="only SELECT"):
        assert_read_only_sql("ATTACH 'other.db' AS other")
    with pytest.raises(DatasetQueryError, match="only SELECT"):
        assert_read_only_sql("INSERT INTO time_entries VALUES (1)")
    with pytest.raises(DatasetQueryError, match="multiple statements"):
        assert_read_only_sql("SELECT 1; DROP TABLE time_entries")
    with pytest.raises(DatasetQueryError, match="disallowed"):
        assert_read_only_sql("SELECT * FROM time_entries WHERE COPY IS NOT NULL")


def test_does_not_flag_keywords_inside_strings_or_comments() -> None:
    assert_read_only_sql("SELECT * FROM t WHERE note = 'DROP TABLE x'")
    assert_read_only_sql("SELECT * FROM t -- DROP TABLE x\nWHERE 1=1")
    assert_read_only_sql("SELECT * FROM t /* CREATE TABLE x */ WHERE 1=1")


def test_wrap_limit_and_preview() -> None:
    wrapped = wrap_limit("SELECT * FROM hours", 50)
    assert wrapped.startswith("SELECT * FROM (")
    assert wrapped.endswith("LIMIT 50")
    assert preview_sql("time_entries", 100) == 'SELECT * FROM "time_entries" LIMIT 100'
    assert preview_sql('weird"name', 10) == 'SELECT * FROM "weird""name" LIMIT 10'


def test_clamp_limit() -> None:
    assert clamp_limit(None, default=100, maximum=1000) == 100
    assert clamp_limit(5000, default=100, maximum=1000) == 1000
    with pytest.raises(DatasetQueryError):
        clamp_limit(0, default=100, maximum=1000)
