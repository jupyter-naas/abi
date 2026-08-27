"""Read-only SQL gate for DatasetService queries.

User SQL is never executed as-is: comments and string literals are stripped
before keyword checks, only SELECT/WITH is allowed, and the statement is
wrapped so a hard LIMIT always applies.
"""

from __future__ import annotations

import re

from naas_abi.apps.nexus.apps.api.app.services.datasets.datasets__schema import (
    DatasetQueryError,
)

MAX_SQL_CHARS = 20_000
DEFAULT_QUERY_LIMIT = 1_000
MAX_QUERY_LIMIT = 5_000
DEFAULT_PREVIEW_LIMIT = 100
MAX_PREVIEW_LIMIT = 1_000

_LINE_COMMENT = re.compile(r"--[^\n]*")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_STRING_LITERAL = re.compile(r"('(?:''|[^'])*'|\"(?:\"\"|[^\"])*\")", re.DOTALL)
_FORBIDDEN = re.compile(
    r"\b("
    r"INSERT|UPDATE|DELETE|MERGE|DROP|CREATE|ALTER|ATTACH|DETACH|"
    r"COPY|PRAGMA|INSTALL|LOAD|EXPORT|IMPORT|CALL|SET|RESET|"
    r"VACUUM|CHECKPOINT|BEGIN|COMMIT|ROLLBACK|GRANT|REVOKE|"
    r"EXECUTE|PREPARE|UNLOAD|TRUNCATE|COMMENT"
    r")\b",
    re.IGNORECASE,
)


def clamp_limit(limit: int | None, *, default: int, maximum: int) -> int:
    if limit is None:
        return default
    if limit < 1:
        raise DatasetQueryError("limit must be >= 1")
    return min(limit, maximum)


def assert_read_only_sql(sql: str) -> str:
    """Return the stripped statement (no trailing semicolon) if it is SELECT-only."""
    raw = (sql or "").strip()
    if not raw:
        raise DatasetQueryError("SQL is required")
    if len(raw) > MAX_SQL_CHARS:
        raise DatasetQueryError("SQL is too long")

    stripped = _strip_comments_and_strings(raw).strip().rstrip(";").strip()
    if not stripped:
        raise DatasetQueryError("SQL is required")
    if ";" in stripped:
        raise DatasetQueryError("multiple statements are not allowed")

    first = stripped.split(None, 1)[0].upper()
    if first not in {"SELECT", "WITH"}:
        raise DatasetQueryError("only SELECT queries are allowed")
    if _FORBIDDEN.search(stripped):
        raise DatasetQueryError("query contains a disallowed statement")
    return raw.rstrip().rstrip(";").strip()


def wrap_limit(sql: str, limit: int) -> str:
    return f"SELECT * FROM (\n{sql}\n) AS _nexus_q LIMIT {int(limit)}"


def preview_sql(name: str, limit: int) -> str:
    ident = name.replace('"', '""')
    return f'SELECT * FROM "{ident}" LIMIT {int(limit)}'


def _strip_comments_and_strings(sql: str) -> str:
    text = _LINE_COMMENT.sub(" ", sql)
    text = _BLOCK_COMMENT.sub(" ", text)
    return _STRING_LITERAL.sub("''", text)
