from contextlib import contextmanager

import pytest
from naas_abi_core.services.document.adapters.secondary.document_sql import DocumentSQL
from naas_abi_core.services.document.DocumentPort import CollectionSpec, FieldSpec


class Compiler(DocumentSQL):
    @contextmanager
    def transaction(self, *, write=False):
        raise AssertionError("Compiler unit tests must not access a database")
        yield  # pragma: no cover


@pytest.fixture(params=[False, True], ids=["sqlite", "postgresql"])
def compiler(request):
    return Compiler(
        postgres=request.param, documents="documents", collections="collections"
    )


def test_predicate_values_are_bound_and_literal_names_are_escaped(compiler):
    params = []
    value = "'; DROP TABLE documents; --"
    predicate = compiler.predicates([("a'quote%", "eq", value)], params)
    assert value not in predicate
    assert "a''quote" in predicate
    assert any(value in parameter for parameter in params)
    if compiler.pg:
        assert "quote%%" in predicate


def test_declarations_merge_additively_and_reject_type_changes(compiler):
    old = CollectionSpec(
        name="records",
        fields=(FieldSpec(name="x", type="int", unique=True),),
        unique_together=(("x", "y"),),
    )
    new = CollectionSpec(
        name="records", fields=(FieldSpec(name="x", type="int", indexed=True),)
    )
    merged = compiler.merge_spec(old, new)
    assert merged.fields[0].indexed and merged.fields[0].unique
    assert merged.unique_together == old.unique_together
    assert compiler.merge_spec(merged, CollectionSpec(name="records")) == merged
    with pytest.raises(ValueError, match="Cannot change declared type"):
        compiler.merge_spec(
            old,
            CollectionSpec(
                name="records", fields=(FieldSpec(name="x", type="string"),)
            ),
        )


def test_index_identifiers_are_bounded_and_namespace_specific(compiler):
    names = {
        compiler.index_name(namespace, "records", ("quoted'field",), unique)
        for namespace in ("one", "two")
        for unique in (False, True)
    }
    assert len(names) == 4
    assert all(len(name) < 63 and name.replace("_", "").isalnum() for name in names)


def test_compound_uniqueness_redeclaration_ignores_field_order(compiler):
    old = CollectionSpec(name="records", unique_together=(("team", "slug"),))
    new = CollectionSpec(name="records", unique_together=(("slug", "team"),))
    assert compiler.merge_spec(old, new) == old


def test_unique_field_index_is_bounded_and_sparse_on_postgresql(compiler):
    spec = CollectionSpec(
        name="records", fields=(FieldSpec(name="x", type="string", unique=True),)
    )
    _, statement = compiler.index_statements("namespace", spec)[0]
    if compiler.pg:
        # A fixed-width hash keeps the B-tree entry bounded for arbitrarily
        # long values; NULLIF still exempts missing/null fields (sparse).
        assert "sha256(" in statement
        assert "NULLIF" in statement
    else:
        assert "document_json_key_v2" in statement


def test_sort_parts_is_a_named_tuple(compiler):
    parts = compiler.sort_parts("x")
    assert (parts.rank, parts.numeric, parts.text) == tuple(parts)
    bounded = parts._replace(text=f"left({parts.text}, 256)")
    assert bounded.rank == parts.rank and bounded.text != parts.text


def test_in_predicate_narrows_with_gin_hint_only_on_postgresql(compiler):
    params: list = []
    predicate = compiler.predicates([("x", "in", ["a", "b"])], params)
    if compiler.pg:
        assert predicate.count("data @> CAST(") == 2
    else:
        assert "data @>" not in predicate


def test_nin_and_empty_in_predicates_never_add_a_gin_hint(compiler):
    for where in ([("x", "nin", ["a", "b"])], [("x", "in", [])]):
        params: list = []
        predicate = compiler.predicates(where, params)
        assert "data @>" not in predicate
