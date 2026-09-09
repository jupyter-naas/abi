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
