from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta, timezone

import pytest
from naas_abi_core.services.document.DocumentPort import (
    CollectionNotFound,
    CollectionSpec,
    DocumentNotFound,
    FieldSpec,
    IDocumentAdapter,
    UniqueViolation,
    VersionConflict,
)

ROUND_TRIP_VALUES = [
    True,
    False,
    0,
    -1,
    1.5,
    0.0,
    "",
    "caf\u00e9",
    None,
    [],
    {},
    [1, [2]],
    {"nested": {"deep": True}},
    datetime(2026, 1, 1, tzinfo=UTC),
    b"\x00\xff",
    {"$t": "bytes", "$v": "AA=="},
    {"a": [datetime(2026, 1, 1, tzinfo=UTC), b"\xff"]},
]


class DocumentSecondaryAdapterContract(ABC):
    def test_generator_filters_cannot_expand_bulk_deletion(self, docs):
        from naas_abi_core.services.document.DocumentService import DocumentService

        service = DocumentService(docs, "module")
        for id, keep in (("a", False), ("b", True), ("c", False), ("d", True)):
            service.put("records", id, {"keep": keep})
        where = [("keep", "eq", False)]
        assert service.count("records", iter(where)) == 2
        assert [
            doc.id for doc in service.iterate("records", where=iter(where), batch=1)
        ] == ["a", "c"]
        assert service.delete_many("records", iter(where)) == 2
        assert [doc.id for doc in service.iterate("records")] == ["b", "d"]

    def test_adapter_generator_filters_are_not_consumed_by_validation(self, docs):
        docs.put("module", "records", "one", {"x": 1}, None)
        docs.put("module", "records", "two", {"x": 2}, None)
        where = [("x", "eq", 1)]
        assert docs.count("module", "records", iter(where)) == 1
        assert [
            doc.id
            for doc in docs.find("module", "records", iter(where), None, 10, None).items
        ] == ["one"]

    def test_cursor_accepts_reordered_and_predicates(self, docs):
        for id in ("a", "b", "c"):
            docs.put("module", "records", id, {"x": 1, "y": True}, None)
        where = [("x", "eq", 1), ("y", "eq", True)]
        first = docs.find("module", "records", where, None, 1, None)
        second = docs.find("module", "records", where[::-1], None, 1, first.cursor)
        assert second.items[0].id == "b"

    def test_catalog_changes_from_peer_are_visible_after_prior_reads(self, docs, peer):
        docs.put("module", "records", "one", {"x": 1}, None)
        peer.ensure_collection(
            "module",
            CollectionSpec(name="records", fields=(FieldSpec(name="x", type="int"),)),
        )
        with pytest.raises(ValueError, match="type int"):
            docs.put("module", "records", "two", {"x": "bad"}, None)
        peer.drop_collection("module", "records")
        with pytest.raises(CollectionNotFound):
            docs.get("module", "records", "one")

    def test_invalid_type_declaration_preserves_existing_data_and_catalog(self, docs):
        docs.put("module", "records", "legacy", {"x": "text"}, None)
        spec = CollectionSpec(name="records", fields=(FieldSpec(name="x", type="int"),))
        with pytest.raises(ValueError, match="module.records.*legacy.*Migrate"):
            docs.ensure_collection("module", spec)
        docs.ensure_collection("module", CollectionSpec(name="records"))
        assert docs.get("module", "records", "legacy").data == {"x": "text"}
        docs.put("module", "records", "new", {"x": "still allowed"}, None)

    def test_delete_zero_is_a_version_conflict_even_for_absent_documents(self, docs):
        with pytest.raises(VersionConflict):
            docs.delete("module", "records", "absent", 0)

    @pytest.mark.parametrize(
        "field", ["a.b'\"$", 'quote"and\\slash', "line\nbreak", "$tag", "caf\u00e9"]
    )
    def test_literal_field_names_preserve_queries_and_uniqueness(self, adapter, field):
        adapter.ensure_collection(
            "module",
            CollectionSpec(
                name="literal",
                fields=(
                    FieldSpec(name=field, type="string", indexed=True, unique=True),
                ),
            ),
        )
        adapter.put("module", "literal", "first", {field: "value"}, None)
        with pytest.raises(UniqueViolation):
            adapter.put("module", "literal", "duplicate", {field: "value"}, None)
        assert adapter.count("module", "literal", [(field, "eq", "value")]) == 1
        assert (
            adapter.find(
                "module", "literal", [(field, "in", ["value"])], (field, "asc"), 1, None
            )
            .items[0]
            .id
            == "first"
        )

    def test_cursor_sort_keys_match_database_order_for_every_value_kind(self, docs):
        values = [
            None,
            False,
            True,
            -1,
            0,
            9,
            10,
            "",
            "a",
            "z",
            datetime(2026, 1, 1, tzinfo=UTC),
            b"",
            b"\x00",
            b"\xff",
            [],
            [1],
            {},
            {"a": 1},
        ]
        for index, value in enumerate(values):
            docs.put("module", "records", f"{index:02}", {"x": value}, None)
        for direction in ("asc", "desc"):
            found, cursor = [], None
            while True:
                page = docs.find("module", "records", (), ("x", direction), 1, cursor)
                found.extend(item.id for item in page.items)
                cursor = page.cursor
                if cursor is None:
                    break
            expected = [f"{index:02}" for index in range(len(values))]
            assert found == (expected if direction == "asc" else expected[::-1])

    @pytest.fixture
    @abstractmethod
    def adapter(self) -> IDocumentAdapter:
        raise NotImplementedError

    @pytest.fixture
    def docs(self, adapter):
        adapter.ensure_collection("module", CollectionSpec(name="records"))
        return adapter

    @pytest.mark.parametrize("value", ROUND_TRIP_VALUES)
    def test_every_value_round_trips(self, docs, value):
        written = docs.put("module", "records", "id", {"value": value}, None)
        read = docs.get("module", "records", "id")
        assert read == written
        assert read.data["value"] == value
        assert type(read.data["value"]) is type(value)
        assert read.created_at.utcoffset() == timedelta(0)
        assert read.updated_at >= read.created_at
        assert read.version == 1
        assert docs.count("module", "records", [("value", "eq", value)]) == 1

    def test_independent_adapters_share_data_constraints_and_atomic_writes(
        self, docs, peer
    ):
        docs.ensure_collection(
            "module",
            CollectionSpec(
                name="records", fields=(FieldSpec(name="x", type="int", unique=True),)
            ),
        )
        docs.put("module", "records", "id", {"x": 1}, None)
        peer.ensure_collection("module", CollectionSpec(name="records"))
        assert peer.get("module", "records", "id").data == {"x": 1}
        with pytest.raises(UniqueViolation):
            peer.put("module", "records", "duplicate", {"x": 1}, None)

        def update(adapter):
            try:
                adapter.put("module", "records", "id", {"x": 2}, 1)
                return True
            except VersionConflict:
                return False

        with ThreadPoolExecutor(max_workers=2) as executor:
            assert sum(executor.map(update, [docs, peer])) == 1
        assert peer.get("module", "records", "id").version == 2

    def test_concurrent_unconditional_writes_increment_every_version(self, docs, peer):
        def update(adapter):
            return adapter.put("module", "records", "id", {}, None).version

        with ThreadPoolExecutor(max_workers=4) as executor:
            assert sorted(executor.map(update, [docs, peer] * 5)) == list(range(1, 11))

    def test_cursor_rejects_other_queries_and_invalid_tokens(self, docs):
        for id in ("a", "b"):
            docs.put("module", "records", id, {"x": 1}, None)
        cursor = docs.find("module", "records", (), None, 1, None).cursor
        for invalid in ("not-a-cursor", "e30=", "bnVsbA==", cursor):
            with pytest.raises(ValueError, match="cursor"):
                docs.find("module", "records", [("x", "eq", 1)], None, 1, invalid)

    def test_typed_fields_reject_incompatible_values_and_type_changes(self, docs):
        docs.ensure_collection(
            "module",
            CollectionSpec(name="records", fields=(FieldSpec(name="x", type="int"),)),
        )
        for value in (True, "1", 1.5):
            with pytest.raises(ValueError, match="type"):
                docs.put("module", "records", "id", {"x": value}, None)
        with pytest.raises(ValueError, match="type"):
            docs.ensure_collection(
                "module",
                CollectionSpec(
                    name="records", fields=(FieldSpec(name="x", type="string"),)
                ),
            )

    def test_numeric_range_preserves_large_integer_precision(self, docs):
        for id, value in [("a", 2**53), ("b", 2**53 + 1), ("c", 2**63 - 1)]:
            docs.put("module", "records", id, {"x": value}, None)
        page = docs.find(
            "module", "records", [("x", "gt", float(2**53))], ("x", "asc"), 1, None
        )
        assert [doc.id for doc in page.items] == ["b"]
        page = docs.find(
            "module",
            "records",
            [("x", "gt", float(2**53))],
            ("x", "asc"),
            1,
            page.cursor,
        )
        assert [doc.id for doc in page.items] == ["c"]

    def test_large_finite_floats_remain_portable_after_read_and_during_paging(
        self, docs
    ):
        values = [
            -1.7976931348623157e308,
            -1e100,
            -1e20,
            1e20,
            1e100,
            1.7976931348623157e308,
        ]
        for index, value in enumerate(values):
            id = str(index)
            docs.put("module", "records", id, {"x": value, "nested": [value]}, None)
            stored = docs.get("module", "records", id)
            assert stored.data == {"x": value, "nested": [value]}
            docs.put("module", "records", id, stored.data, stored.version)
        cursor, found = None, []
        while True:
            page = docs.find("module", "records", (), ("x", "asc"), 1, cursor)
            found.extend(doc.id for doc in page.items)
            cursor = page.cursor
            if cursor is None:
                break
        assert found == [str(index) for index in range(len(values))]

    def test_byte_sort_and_exact_nested_array_membership(self, docs):
        for id, value in [("a", b"\xff"), ("b", b"\x00"), ("c", b"\x01")]:
            docs.put(
                "module", "records", id, {"x": value, "array": [{"a": [1, True]}]}, None
            )
        page = docs.find(
            "module",
            "records",
            [("array", "contains", {"a": [1.0, True]})],
            ("x", "asc"),
            10,
            None,
        )
        assert [doc.id for doc in page.items] == ["b", "c", "a"]
        assert (
            docs.count("module", "records", [("array", "contains", {"a": [1, 1]})]) == 0
        )

    def test_collection_lifecycle_and_namespaces(self, docs):
        docs.put("module", "records", "id", {}, None)
        docs.ensure_collection("module", CollectionSpec(name="records"))
        docs.ensure_collection("other", CollectionSpec(name="records"))
        assert docs.collections("module") == ["records"]
        assert docs.collections("unknown") == []
        with pytest.raises(DocumentNotFound):
            docs.get("other", "records", "id")
        docs.drop_collection("other", "records")
        assert docs.get("module", "records", "id").version == 1
        with pytest.raises(CollectionNotFound):
            docs.put("other", "records", "id", {}, None)
        docs.drop_collection("module", "records")
        docs.ensure_collection("module", CollectionSpec(name="records"))
        assert docs.count("module", "records", ()) == 0

    @pytest.mark.parametrize("operation", ["get", "put", "delete", "find", "count"])
    def test_missing_collection_raises(self, adapter, operation):
        args = {
            "get": ("id",),
            "put": ("id", {}, None),
            "delete": ("id", None),
            "find": ((), None, 10, None),
            "count": ((),),
        }
        with pytest.raises(CollectionNotFound):
            getattr(adapter, operation)("none", "missing", *args[operation])

    def test_compare_and_swap(self, docs):
        first = docs.put("module", "records", "id", {"old": True}, 0)
        second = docs.put("module", "records", "id", {"new": True}, first.version)
        assert second.version == 2
        assert second.created_at == first.created_at
        assert second.data == {"new": True}
        for version in (0, first.version):
            with pytest.raises(VersionConflict):
                docs.put("module", "records", "id", {}, version)
            with pytest.raises(VersionConflict):
                docs.delete("module", "records", "id", version)
        with pytest.raises(VersionConflict):
            docs.put("module", "records", "missing", {}, 1)
        docs.delete("module", "records", "id", second.version)
        with pytest.raises(DocumentNotFound):
            docs.get("module", "records", "id")
        docs.delete("module", "records", "id", None)
        with pytest.raises(VersionConflict):
            docs.delete("module", "records", "id", 2)

    def test_concurrent_cas_has_one_winner(self, docs):
        docs.put("module", "records", "id", {}, 0)

        def update(i):
            try:
                docs.put("module", "records", "id", {"winner": i}, 1)
                return True
            except VersionConflict:
                return False

        with ThreadPoolExecutor(max_workers=4) as executor:
            assert sum(executor.map(update, range(4))) == 1

    def test_ordering_is_numeric_and_paging_handles_ties_and_nulls(self, docs):
        docs.ensure_collection(
            "module",
            CollectionSpec(
                name="records", fields=(FieldSpec(name="n", type="int", indexed=True),)
            ),
        )
        for id, data in [
            ("a", {}),
            ("b", {"n": None}),
            ("c", {"n": 9}),
            ("d", {"n": 10}),
            ("e", {"n": 10}),
        ]:
            docs.put("module", "records", id, data, None)
        for direction, expected in [("asc", list("abcde")), ("desc", list("edcba"))]:
            cursor = None
            found = []
            while True:
                page = docs.find("module", "records", (), ("n", direction), 2, cursor)
                found.extend(doc.id for doc in page.items)
                cursor = page.cursor
                if cursor is None:
                    break
            assert found == expected

    def test_cursor_is_stable_after_insert_and_deleted_anchor(self, docs):
        for id in ("b", "d", "f"):
            docs.put("module", "records", id, {"n": ord(id)}, None)
        page = docs.find("module", "records", (), ("n", "asc"), 2, None)
        docs.put("module", "records", "a", {"n": 1}, None)
        docs.put("module", "records", "e", {"n": ord("e")}, None)
        docs.delete("module", "records", "d", None)
        page = docs.find("module", "records", (), ("n", "asc"), 2, page.cursor)
        assert [doc.id for doc in page.items] == ["e", "f"]
        assert page.cursor is None

    @pytest.mark.parametrize(
        ("where", "expected"),
        [
            ([("x", "eq", None)], ["null"]),
            ([("x", "ne", None)], ["array", "bool", "nine", "object", "ten", "text"]),
            ([("x", "exists", False)], ["missing"]),
            ([("x", "eq", True)], ["bool"]),
            ([("x", "gt", 9)], ["ten"]),
            ([("x", "gte", 9), ("x", "lte", 10)], ["nine", "ten"]),
            ([("x", "lt", 10)], ["nine"]),
            ([("x", "in", [9, None])], ["nine", "null"]),
            ([("x", "nin", [9, None])], ["array", "bool", "object", "ten", "text"]),
            ([("x", "in", [])], []),
            ([("x", "contains", 9)], ["array"]),
            ([("x", "contains", {"z": 2})], []),
            ([("x", "eq", {"z": 2, "a": 1})], ["object"]),
        ],
    )
    def test_predicates(self, docs, where, expected):
        for id, data in [
            ("missing", {}),
            ("null", {"x": None}),
            ("bool", {"x": True}),
            ("nine", {"x": 9}),
            ("ten", {"x": 10}),
            ("text", {"x": "10"}),
            ("array", {"x": [9, {"z": 2, "a": 1}]}),
            ("object", {"x": {"a": 1, "z": 2}}),
        ]:
            docs.put("module", "records", id, data, None)
        assert [
            doc.id
            for doc in docs.find("module", "records", where, None, 100, None).items
        ] == expected
        assert docs.count("module", "records", where) == len(expected)

    def test_unique_sparse_compound_and_additive_declarations(self, docs):
        spec = CollectionSpec(
            name="records",
            fields=(FieldSpec(name="email", type="string", unique=True),),
            unique_together=(("team", "slug"),),
        )
        docs.ensure_collection("module", spec)
        docs.ensure_collection("module", CollectionSpec(name="records"))
        for id, data in [
            ("a", {}),
            ("b", {}),
            ("c", {"email": None}),
            ("d", {"email": None}),
        ]:
            docs.put("module", "records", id, data, None)
        docs.put(
            "module", "records", "one", {"email": "a", "team": "t", "slug": "s"}, None
        )
        for data in ({"email": "a"}, {"team": "t", "slug": "s"}):
            with pytest.raises(UniqueViolation):
                docs.put("module", "records", "two", data, None)
        assert docs.count("module", "records", ()) == 5
        docs.ensure_collection("other", spec)
        docs.put(
            "other", "records", "one", {"email": "a", "team": "t", "slug": "s"}, None
        )

    def test_adding_unique_constraint_checks_existing_data_and_rolls_back(self, docs):
        for id in ("a", "b"):
            docs.put("module", "records", id, {"x": 1}, None)
        with pytest.raises(UniqueViolation):
            docs.ensure_collection(
                "module",
                CollectionSpec(
                    name="records",
                    fields=(FieldSpec(name="x", type="int", unique=True),),
                ),
            )
        docs.put("module", "records", "c", {"x": 1}, None)
        docs.delete("module", "records", "a", None)
        docs.delete("module", "records", "b", None)
        docs.ensure_collection(
            "module",
            CollectionSpec(
                name="records", fields=(FieldSpec(name="x", type="int", unique=True),)
            ),
        )

    def test_naive_datetime_is_rejected_recursively(self, docs):
        naive = datetime(2026, 1, 1)  # noqa: DTZ001 - exercise naive-date rejection
        with pytest.raises(ValueError, match="timezone"):
            docs.put(
                "module",
                "records",
                "bad",
                {"nested": [naive]},
                None,
            )

    def test_datetime_comparison_normalizes_offsets(self, docs):
        first = datetime(2026, 1, 1, 1, tzinfo=timezone(timedelta(hours=2)))
        second = datetime(2026, 1, 1, tzinfo=UTC)
        docs.put("module", "records", "a", {"date": first}, None)
        docs.put("module", "records", "b", {"date": second}, None)
        page = docs.find(
            "module", "records", [("date", "lt", second)], ("date", "asc"), 10, None
        )
        assert [doc.id for doc in page.items] == ["a"]

    def test_names_and_predicate_values_are_not_sql(self, adapter):
        name = "x'%s?; DROP TABLE abi_documents; --"
        field = "a.b'\"$"
        adapter.ensure_collection(
            name,
            CollectionSpec(
                name=name, fields=(FieldSpec(name=field, type="string", unique=True),)
            ),
        )
        adapter.put(name, name, name, {field: name}, None)
        page = adapter.find(name, name, [(field, "eq", name)], (field, "asc"), 1, None)
        assert page.items[0].id == name
