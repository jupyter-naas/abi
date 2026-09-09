"""Portable document storage: top-level AND predicates and per-document atomicity."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol, TypeAlias, runtime_checkable

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

Value: TypeAlias = (
    str
    | int
    | float
    | bool
    | None
    | datetime
    | bytes
    | list["Value"]
    | dict[str, "Value"]
)
Operator = Literal[
    "eq", "ne", "lt", "lte", "gt", "gte", "in", "nin", "contains", "exists"
]
Predicate: TypeAlias = tuple[str, Operator, Value]
OrderBy: TypeAlias = tuple[str, Literal["asc", "desc"]] | None


class DocumentNotFound(Exception):
    pass


class CollectionNotFound(Exception):
    pass


class VersionConflict(Exception):
    pass


class UniqueViolation(Exception):
    pass


def validate_name(value: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ValueError("Names must be nonempty strings without NUL characters")
    value.encode("utf-8")
    return value


class FieldSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    type: Literal["string", "int", "float", "bool", "datetime", "bytes", "json"]
    indexed: bool = False
    unique: bool = False

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        return validate_name(value)


class CollectionSpec(BaseModel):
    """Optional type declarations and additive index/uniqueness constraints."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    fields: tuple[FieldSpec, ...] = ()
    unique_together: tuple[tuple[str, ...], ...] = ()

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        return validate_name(value)

    @model_validator(mode="after")
    def valid_fields(self) -> CollectionSpec:
        names = [field.name for field in self.fields]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate field declarations")
        for group in self.unique_together:
            if not group or len(group) != len(set(group)):
                raise ValueError(
                    "unique_together must contain nonempty groups of distinct fields"
                )
            for name in group:
                validate_name(name)
        return self


@dataclass(frozen=True)
class Document:
    id: str
    data: dict[str, Value]
    created_at: datetime
    updated_at: datetime
    version: int


@dataclass(frozen=True)
class Page:
    items: list[Document]
    cursor: str | None


def validate_value(value: Value) -> None:
    if value is None or type(value) in (bool, bytes):
        return
    if type(value) is str:
        if "\x00" in value:
            raise ValueError("Document strings cannot contain NUL characters")
        value.encode("utf-8")
    elif type(value) is int:
        if not -(2**63) <= value < 2**63:
            raise ValueError("Document integers must fit in signed 64 bits")
    elif type(value) is float:
        if not math.isfinite(value):
            raise ValueError("Document floats must be finite")
    elif isinstance(value, datetime):
        if value.utcoffset() is None:
            raise ValueError("Document datetimes must be timezone-aware")
    elif isinstance(value, list):
        for item in value:
            validate_value(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("Document keys must be strings")  # noqa: TRY004 - uniform payload validation error
            validate_value(key)
            validate_value(item)
    else:
        raise ValueError(f"Unsupported document value type: {type(value).__name__}")


def validate_data(data: dict[str, Value], spec: CollectionSpec | None = None) -> None:
    if not isinstance(data, dict):
        raise ValueError("Document data must be a dictionary")  # noqa: TRY004 - uniform payload validation error
    validate_value(data)
    if spec is None:
        return
    types: dict[str, tuple[type, ...]] = {
        "string": (str,),
        "int": (int,),
        "float": (float, int),
        "bool": (bool,),
        "datetime": (datetime,),
        "bytes": (bytes,),
    }
    for field in spec.fields:
        value = data.get(field.name)
        if (
            value is not None
            and field.type != "json"
            and type(value) not in types[field.type]
        ):
            raise ValueError(f"Field {field.name!r} must have type {field.type}")


def validate_version(version: int | None) -> None:
    if version is not None and (type(version) is not int or version < 0):
        raise ValueError("if_version must be a nonnegative integer or None")


def validate_query(
    where: Sequence[Predicate], order_by: OrderBy = None, limit: int = 100
) -> None:
    if type(limit) is not int or limit < 1:
        raise ValueError("Page size must be a positive integer")
    if order_by is not None:
        if len(order_by) != 2 or order_by[1] not in ("asc", "desc"):
            raise ValueError("order_by must be (field, 'asc'|'desc')")
        validate_name(order_by[0])
    for predicate in where:
        if len(predicate) != 3:
            raise ValueError("Predicates must contain (field, operator, value)")
        field, operator, value = predicate
        validate_name(field)
        if operator not in (
            "eq",
            "ne",
            "lt",
            "lte",
            "gt",
            "gte",
            "in",
            "nin",
            "contains",
            "exists",
        ):
            raise ValueError(f"Unsupported predicate operator: {operator}")
        validate_value(value)
        if operator == "exists" and type(value) is not bool:
            raise ValueError("exists requires a boolean")
        if operator in ("in", "nin") and not isinstance(value, list):
            raise ValueError("in/nin require a list")
        if operator in ("lt", "lte", "gt", "gte") and (
            value is None or isinstance(value, (list, dict))
        ):
            raise ValueError("Range predicates require a non-null scalar")


@runtime_checkable
class IDocumentAdapter(Protocol):
    def close(self) -> None:
        """Release adapter resources; subsequent use is invalid."""
        ...

    def ensure_collection(self, namespace: str, spec: CollectionSpec) -> None: ...
    def drop_collection(self, namespace: str, collection: str) -> None: ...
    def collections(self, namespace: str) -> list[str]: ...
    def put(
        self,
        namespace: str,
        collection: str,
        id: str,
        data: dict[str, Value],
        if_version: int | None,
    ) -> Document: ...
    def get(self, namespace: str, collection: str, id: str) -> Document: ...
    def delete(
        self, namespace: str, collection: str, id: str, if_version: int | None
    ) -> None: ...
    def find(
        self,
        namespace: str,
        collection: str,
        where: Sequence[Predicate],
        order_by: OrderBy,
        limit: int,
        cursor: str | None,
    ) -> Page: ...
    def count(
        self, namespace: str, collection: str, where: Sequence[Predicate]
    ) -> int: ...
