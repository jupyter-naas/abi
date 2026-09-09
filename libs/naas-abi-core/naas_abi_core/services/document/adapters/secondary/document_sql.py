"""Shared SQL implementation; all backend details remain in secondary adapters."""

from __future__ import annotations

import base64
import hashlib
import json
from abc import ABC, abstractmethod
from collections.abc import Sequence
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from typing import Any, cast

from naas_abi_core.services.document.adapters.secondary.document_codec import (
    decode,
    dumps,
    encode,
    storage_key,
)
from naas_abi_core.services.document.DocumentPort import (
    CollectionNotFound,
    CollectionSpec,
    Document,
    DocumentNotFound,
    FieldSpec,
    OrderBy,
    Page,
    Predicate,
    Value,
    VersionConflict,
    validate_data,
    validate_name,
    validate_query,
    validate_value,
    validate_version,
)


class DocumentSQL(ABC):
    """Compile SQL using adapter-owned identifiers and bound document values.

    Field literals pass through literal(); operators and directions are
    allowlisted. The B608 annotations below cover that reviewed construction.
    """

    def __init__(self, *, postgres: bool, documents: str, collections: str):
        self.pg = postgres
        self.documents_table = documents
        self.collections_table = collections
        self.p = "%s" if postgres else "?"

    @abstractmethod
    def transaction(self, *, write: bool = False) -> AbstractContextManager[Any]: ...

    def literal(self, value: str) -> str:
        value = value.replace("'", "''")
        if self.pg:
            value = value.replace("%", "%%")
        return "'" + value + "'"

    def field(self, name: str) -> str:
        key = storage_key(name)
        if self.pg:
            return f"(data -> {self.literal(key)})"
        path = "$." + json.dumps(key, ensure_ascii=False)
        return f"(data -> {self.literal(path)})"

    def kind(self, expression: str) -> str:
        return f"jsonb_typeof({expression})" if self.pg else f"json_type({expression})"

    def text(self, expression: str) -> str:
        if self.pg:
            return f"({expression} #>> '{{}}')"
        return f"json_extract({expression}, '$')"

    def child_text(self, expression: str, key: str) -> str:
        if self.pg:
            return f"({expression} ->> {self.literal(key)})"
        return f"json_extract({expression}, {self.literal('$.' + json.dumps(key))})"

    def sort_parts(self, field: str) -> list[str]:
        """Portable scalar order; containers tie by type, then document ID."""
        expression = self.field(field)
        kind = self.kind(expression)
        tag = self.child_text(expression, "$t")
        value = self.child_text(expression, "$v")
        numeric_types = "'number'" if self.pg else "'integer','real'"
        bool_types = "'boolean'" if self.pg else "'true','false'"
        string_type = "'string'" if self.pg else "'text'"
        rank = (
            f"CASE WHEN {kind} IN ({bool_types}) THEN 1 "
            f"WHEN {kind} IN ({numeric_types}) THEN 2 "
            f"WHEN {kind} = {string_type} THEN 3 "
            f"WHEN {tag} = 'datetime' THEN 4 WHEN {tag} = 'bytes' THEN 5 "
            f"WHEN {kind} = 'array' THEN 6 WHEN {kind} = 'object' THEN 7 ELSE 0 END"
        )
        scalar = self.text(expression)
        number = f"CAST({scalar} AS NUMERIC)" if self.pg else scalar
        boolean = (
            f"CASE WHEN {scalar} = 'true' THEN 1 ELSE 0 END" if self.pg else scalar
        )
        numeric = f"CASE WHEN {kind} IN ({numeric_types}) THEN {number} WHEN {kind} IN ({bool_types}) THEN {boolean} ELSE 0 END"
        binary = (
            f"encode(decode({value}, 'base64'), 'hex')"
            if self.pg
            else f"document_bytes_key({value})"
        )
        collation = '"C"' if self.pg else "BINARY"
        text = f"(CASE WHEN {kind} = {string_type} THEN {scalar} WHEN {tag} = 'datetime' THEN {value} WHEN {tag} = 'bytes' THEN {binary} ELSE '' END COLLATE {collation})"
        return [f"({rank})", f"({numeric})", text]

    def equal(self, expression: str, value: Value, params: list[Any]) -> str:
        params.append(dumps(encode(value)))
        if self.pg:
            return f"COALESCE({expression} = CAST({self.p} AS JSONB), FALSE)"
        return f"document_equal({expression}, {self.p})"

    def predicates(self, where: Sequence[Predicate], params: list[Any]) -> str:
        clauses = []
        for field, operator, value in where:
            expression = self.field(field)
            if operator == "exists":
                clause = f"{expression} IS {'NOT ' if value else ''}NULL"
            elif operator in ("eq", "ne"):
                clause = self.equal(expression, value, params)
                if operator == "ne":
                    clause = f"{expression} IS NOT NULL AND NOT ({clause})"
                elif self.pg:
                    # GIN narrows candidates; equality still enforces exact objects/arrays.
                    params.append(dumps({storage_key(field): encode(value)}))
                    clause += f" AND data @> CAST({self.p} AS JSONB)"
            elif operator in ("in", "nin"):
                assert isinstance(value, list)
                clause = (
                    " OR ".join(self.equal(expression, item, params) for item in value)
                    or "FALSE"
                )
                clause = f"({clause})"
                if operator == "nin":
                    clause = f"{expression} IS NOT NULL AND NOT {clause}"
            elif operator == "contains":
                if self.pg:
                    item = "member.value"
                    source = f"jsonb_array_elements(CASE WHEN {self.kind(expression)} = 'array' THEN {expression} ELSE '[]'::jsonb END) AS member(value)"
                else:
                    item = f"({expression} -> ('$[' || member.key || ']'))"
                    source = f"json_each(CASE WHEN {self.kind(expression)} = 'array' THEN {expression} ELSE '[]' END) AS member"
                clause = f"EXISTS (SELECT 1 FROM {source} WHERE {self.equal(item, value, params)})"
            else:
                rank, numeric, text = self.sort_parts(field)
                value_rank, value_numeric, value_text = self.value_sort_parts(value)
                compare = {"lt": "<", "lte": "<=", "gt": ">", "gte": ">="}[operator]
                target = value_numeric if value_rank in (1, 2) else value_text
                numeric_comparison = self.pg and value_rank in (1, 2)
                params.extend(
                    [value_rank, str(target) if numeric_comparison else target]
                )
                placeholder = (
                    f"CAST({self.p} AS NUMERIC)" if numeric_comparison else self.p
                )
                clause = f"{rank} = {self.p} AND {numeric if value_rank in (1, 2) else text} {compare} {placeholder}"
            clauses.append(f"({clause})")
        return " AND ".join(clauses) or "TRUE"

    @staticmethod
    def value_sort_parts(value: Value) -> tuple[int, int | float, str]:
        if value is None:
            return (0, 0, "")
        if isinstance(value, bool):
            return (1, int(value), "")
        if isinstance(value, (int, float)):
            return (2, value, "")
        if isinstance(value, str):
            return (3, 0, value)
        if isinstance(value, datetime):
            return (4, 0, encode(value)["$v"])
        if isinstance(value, bytes):
            return (5, 0, value.hex())
        return (6 if isinstance(value, list) else 7, 0, "")

    def require_collection(
        self,
        connection: Any,
        namespace: str,
        collection: str,
        *,
        exclusive: bool = False,
    ) -> CollectionSpec:
        validate_name(namespace)
        validate_name(collection)
        lock = (" FOR UPDATE" if exclusive else " FOR SHARE") if self.pg else ""
        row = connection.execute(
            f"SELECT spec FROM {self.collections_table} WHERE namespace = {self.p} AND name = {self.p}{lock}",  # nosec B608
            (namespace, collection),
        ).fetchone()
        if row is None:
            raise CollectionNotFound(
                f"Collection {namespace}.{collection} does not exist"
            )
        return CollectionSpec.model_validate_json(row[0])

    @staticmethod
    def merge_spec(old: CollectionSpec, new: CollectionSpec) -> CollectionSpec:
        fields = {field.name: field for field in old.fields}
        for field in new.fields:
            previous = fields.get(field.name)
            if previous is not None:
                if previous.type != field.type:
                    raise ValueError(
                        f"Cannot change declared type of {field.name!r}; migrate the data explicitly"
                    )
                field = FieldSpec(
                    name=field.name,
                    type=field.type,
                    indexed=field.indexed or previous.indexed,
                    unique=field.unique or previous.unique,
                )
            fields[field.name] = field
        return CollectionSpec(
            name=new.name,
            fields=tuple(fields.values()),
            unique_together=tuple(
                dict.fromkeys(old.unique_together + new.unique_together)
            ),
        )

    def index_name(
        self, namespace: str, collection: str, fields: tuple[str, ...], unique: bool
    ) -> str:
        digest = hashlib.sha256(
            dumps([namespace, collection, fields, unique]).encode()
        ).hexdigest()[:40]
        return "abi_doc_" + digest

    def indexes(self, spec: CollectionSpec) -> list[tuple[tuple[str, ...], bool]]:
        result: list[tuple[tuple[str, ...], bool]] = [
            ((field.name,), False) for field in spec.fields if field.indexed
        ]
        result.extend(((field.name,), True) for field in spec.fields if field.unique)
        result.extend((group, True) for group in spec.unique_together)
        return list(dict.fromkeys(result))

    def ensure_collection(self, namespace: str, spec: CollectionSpec) -> None:
        validate_name(namespace)
        with self.transaction(write=True) as connection:
            connection.execute(
                f"INSERT INTO {self.collections_table} (namespace, name, spec) VALUES ({self.p}, {self.p}, {self.p}) ON CONFLICT (namespace, name) DO NOTHING",  # nosec B608
                (
                    namespace,
                    spec.name,
                    CollectionSpec(name=spec.name).model_dump_json(),
                ),
            )
            old = self.require_collection(
                connection, namespace, spec.name, exclusive=True
            )
            merged = self.merge_spec(old, spec)
            if merged == old:
                return
            # Type declarations also apply to existing records. Stream validation
            # before DDL so incompatible declarations never partly take effect.
            if merged.fields != old.fields:
                rows = connection.execute(
                    f"SELECT data FROM {self.documents_table} WHERE namespace = {self.p} AND collection = {self.p}",  # nosec B608
                    (namespace, spec.name),
                )
                while batch := rows.fetchmany(500):
                    for row in batch:
                        validate_data(self.read_data(row[0]), merged)
            for fields, unique in self.indexes(merged):
                name = self.index_name(namespace, spec.name, fields, unique)
                expressions = []
                for field in fields:
                    raw = self.field(field)
                    if unique:
                        expressions.append(
                            f"(NULLIF({raw}, 'null'::jsonb))"
                            if self.pg
                            else f"document_json_key({raw})"
                        )
                    else:
                        expressions.extend(self.sort_parts(field))
                condition = f"namespace = {self.literal(namespace)} AND collection = {self.literal(spec.name)}"
                connection.execute(
                    f"CREATE {'UNIQUE ' if unique else ''}INDEX IF NOT EXISTS {name} ON {self.documents_table} ({', '.join(expressions)}) WHERE {condition}",
                    (),
                )
            connection.execute(
                f"UPDATE {self.collections_table} SET spec = {self.p} WHERE namespace = {self.p} AND name = {self.p}",  # nosec B608
                (merged.model_dump_json(), namespace, spec.name),
            )

    def drop_collection(self, namespace: str, collection: str) -> None:
        with self.transaction(write=True) as connection:
            spec = self.require_collection(
                connection, namespace, collection, exclusive=True
            )
            connection.execute(
                f"DELETE FROM {self.documents_table} WHERE namespace = {self.p} AND collection = {self.p}",  # nosec B608
                (namespace, collection),
            )
            for fields, unique in self.indexes(spec):
                name = self.index_name(namespace, collection, fields, unique)
                # PostgreSQL index names live in the table's schema.
                prefix = self.documents_table.rsplit(".", 1)[0] + "." if self.pg else ""
                connection.execute(f"DROP INDEX IF EXISTS {prefix}{name}", ())
            connection.execute(
                f"DELETE FROM {self.collections_table} WHERE namespace = {self.p} AND name = {self.p}",  # nosec B608
                (namespace, collection),
            )

    def collections(self, namespace: str) -> list[str]:
        validate_name(namespace)
        with self.transaction() as connection:
            return sorted(
                row[0]
                for row in connection.execute(
                    f"SELECT name FROM {self.collections_table} WHERE namespace = {self.p}",  # nosec B608
                    (namespace,),
                ).fetchall()
            )

    @staticmethod
    def read_data(raw: Any) -> dict[str, Value]:
        return cast(
            dict[str, Value], decode(json.loads(raw) if isinstance(raw, str) else raw)
        )

    def document(self, row: Any) -> Document:
        return Document(
            id=row[0],
            data=self.read_data(row[1]),
            created_at=datetime.fromisoformat(row[2])
            if isinstance(row[2], str)
            else row[2],
            updated_at=datetime.fromisoformat(row[3])
            if isinstance(row[3], str)
            else row[3],
            version=row[4],
        )

    def put(
        self,
        namespace: str,
        collection: str,
        id: str,
        data: dict[str, Value],
        if_version: int | None,
    ) -> Document:
        validate_name(id)
        validate_version(if_version)
        validate_data(data)
        with self.transaction(write=True) as connection:
            spec = self.require_collection(connection, namespace, collection)
            validate_data(data, spec)
            raw = dumps(encode(data))
            now = datetime.now(UTC).isoformat(timespec="microseconds")
            json_param = f"CAST({self.p} AS JSONB)" if self.pg else self.p
            returning = " RETURNING id, data, created_at, updated_at, version"
            params: tuple[Any, ...]
            if if_version is not None and if_version > 0:
                query = f"UPDATE {self.documents_table} SET data = {json_param}, updated_at = {self.p}, version = version + 1 WHERE namespace = {self.p} AND collection = {self.p} AND id = {self.p} AND version = {self.p}"
                params = (raw, now, namespace, collection, id, if_version)
            else:
                query = f"INSERT INTO {self.documents_table} AS current (namespace, collection, id, data, created_at, updated_at, version) VALUES ({self.p}, {self.p}, {self.p}, {json_param}, {self.p}, {self.p}, 1) ON CONFLICT (namespace, collection, id) "
                query += (
                    "DO NOTHING"
                    if if_version == 0
                    else "DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at, version = current.version + 1"
                )
                params = (namespace, collection, id, raw, now, now)
            row = connection.execute(query + returning, params).fetchone()
            if row is None:
                raise VersionConflict(
                    f"Document {collection}/{id} does not have version {if_version}"
                )
            return self.document(row)

    def get(self, namespace: str, collection: str, id: str) -> Document:
        validate_name(id)
        with self.transaction() as connection:
            self.require_collection(connection, namespace, collection)
            row = connection.execute(
                f"SELECT id, data, created_at, updated_at, version FROM {self.documents_table} WHERE namespace = {self.p} AND collection = {self.p} AND id = {self.p}",  # nosec B608
                (namespace, collection, id),
            ).fetchone()
            if row is None:
                raise DocumentNotFound(f"Document {collection}/{id} does not exist")
            return self.document(row)

    def delete(
        self, namespace: str, collection: str, id: str, if_version: int | None
    ) -> None:
        validate_name(id)
        validate_version(if_version)
        with self.transaction(write=True) as connection:
            self.require_collection(connection, namespace, collection)
            params: list[Any] = [namespace, collection, id]
            condition = ""
            if if_version is not None:
                condition = f" AND version = {self.p}"
                params.append(if_version)
            result = connection.execute(
                f"DELETE FROM {self.documents_table} WHERE namespace = {self.p} AND collection = {self.p} AND id = {self.p}{condition}",  # nosec B608
                params,
            )
            if if_version is not None and result.rowcount == 0:
                raise VersionConflict(
                    f"Document {collection}/{id} does not have version {if_version}"
                )

    def find(
        self,
        namespace: str,
        collection: str,
        where: Sequence[Predicate],
        order_by: OrderBy,
        limit: int,
        cursor: str | None,
    ) -> Page:
        validate_query(where, order_by, limit)
        params: list[Any] = [namespace, collection]
        condition = self.predicates(where, params)
        collation = '"C"' if self.pg else "BINARY"
        parts = ([] if order_by is None else self.sort_parts(order_by[0])) + [
            f"id COLLATE {collation}"
        ]
        descending = order_by is not None and order_by[1] == "desc"
        fingerprint = hashlib.sha256(
            dumps(
                encode(
                    [
                        namespace,
                        collection,
                        [list(p) for p in where],
                        list(order_by) if order_by else None,
                    ]
                )
            ).encode()
        ).hexdigest()
        if cursor is not None:
            try:
                token = json.loads(
                    base64.b64decode(cursor, altchars=b"-_", validate=True)
                )
                if (
                    token["v"] != 1
                    or token["q"] != fingerprint
                    or len(token["key"]) != len(parts)
                ):
                    raise ValueError
                key = token["key"]
                if not isinstance(key, list) or not isinstance(key[-1], str):
                    raise TypeError
                validate_name(key[-1])
                validate_value(key)
                if order_by is not None and (
                    type(key[0]) is not int
                    or not 0 <= key[0] <= 7
                    or type(key[1]) not in (int, float)
                    or not isinstance(key[2], str)
                ):
                    raise ValueError
            except (ValueError, TypeError, KeyError, IndexError) as exc:
                raise ValueError("Invalid cursor for this query") from exc
            placeholders = [self.p] * len(parts)
            if self.pg and order_by is not None:
                placeholders[1] = f"CAST({self.p} AS NUMERIC)"
                key[1] = str(key[1])
            condition += f" AND ({', '.join(parts)}) {'<' if descending else '>'} ({', '.join(placeholders)})"
            params.extend(key)
        params.append(limit + 1)
        ordering = ", ".join(
            part + (" DESC" if descending else " ASC") for part in parts
        )
        with self.transaction() as connection:
            self.require_collection(connection, namespace, collection)
            rows = connection.execute(
                f"SELECT id, data, created_at, updated_at, version FROM {self.documents_table} WHERE namespace = {self.p} AND collection = {self.p} AND ({condition}) ORDER BY {ordering} LIMIT {self.p}",  # nosec B608
                params,
            ).fetchall()
        items = [self.document(row) for row in rows[:limit]]
        next_cursor = None
        if len(rows) > limit:
            last = items[-1]
            last_key = (
                []
                if order_by is None
                else list(self.value_sort_parts(last.data.get(order_by[0])))
            ) + [last.id]
            next_cursor = base64.urlsafe_b64encode(
                dumps({"v": 1, "q": fingerprint, "key": last_key}).encode()
            ).decode()
        return Page(items, next_cursor)

    def count(self, namespace: str, collection: str, where: Sequence[Predicate]) -> int:
        validate_query(where)
        params: list[Any] = [namespace, collection]
        condition = self.predicates(where, params)
        with self.transaction() as connection:
            self.require_collection(connection, namespace, collection)
            return connection.execute(
                f"SELECT COUNT(*) FROM {self.documents_table} WHERE namespace = {self.p} AND collection = {self.p} AND ({condition})",  # nosec B608
                params,
            ).fetchone()[0]
