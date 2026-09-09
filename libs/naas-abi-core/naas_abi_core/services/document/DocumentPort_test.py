from datetime import UTC, datetime
from decimal import Decimal

import pytest
from naas_abi_core.services.document.DocumentPort import (
    CollectionSpec,
    FieldSpec,
    validate_data,
    validate_name,
    validate_query,
    validate_value,
    validate_version,
)


@pytest.mark.parametrize("name", ["", "a\x00b", "\ud800", None, 1])
def test_names_reject_invalid_database_text(name):
    with pytest.raises(ValueError):
        validate_name(name)


@pytest.mark.parametrize(
    "value",
    [
        -(2**63),
        2**63 - 1,
        datetime(2026, 1, 1, tzinfo=UTC),
        {"": [None, b"\x00", True, 1.5]},
    ],
)
def test_portable_values_accept_boundary_and_nested_types(value):
    validate_value(value)


@pytest.mark.parametrize(
    "value",
    [
        -(2**63) - 1,
        2**63,
        float("inf"),
        {"nested": [Decimal(1)]},
        {1: "value"},
        "\x00",
        "\ud800",
    ],
)
def test_portable_values_reject_invalid_nested_values(value):
    with pytest.raises(ValueError):
        validate_value(value)


def test_declared_integer_does_not_accept_boolean_but_allows_missing_and_null():
    spec = CollectionSpec(name="records", fields=(FieldSpec(name="n", type="int"),))
    for data in ({}, {"n": None}, {"n": 1}, {"extra": [True]}):
        validate_data(data, spec)
    with pytest.raises(ValueError, match="must have type int"):
        validate_data({"n": True}, spec)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"fields": (FieldSpec(name="x", type="int"), FieldSpec(name="x", type="int"))},
        {"unique_together": ((),)},
        {"unique_together": (("x", "x"),)},
    ],
)
def test_collection_rejects_ambiguous_declarations(kwargs):
    with pytest.raises(ValueError):
        CollectionSpec(name="records", **kwargs)


@pytest.mark.parametrize("version", [True, -1, 1.0, "1"])
def test_version_rejects_coercible_nonintegers(version):
    with pytest.raises(ValueError):
        validate_version(version)


@pytest.mark.parametrize(
    "where",
    [
        [("x", "exists", 1)],
        [("x", "in", "value")],
        [("x", "gt", None)],
        [("x", "contains")],
    ],
)
def test_query_rejects_invalid_operator_arguments(where):
    with pytest.raises(ValueError):
        validate_query(where)
