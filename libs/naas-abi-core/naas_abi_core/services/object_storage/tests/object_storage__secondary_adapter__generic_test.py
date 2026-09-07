"""Shared conformance suite for object storage secondary adapters.

Subclass ``ObjectStorageSecondaryAdapterContract`` from an adapter's own test
module and supply the ``adapter`` fixture. Every adapter is then held to the
same observable behaviour without restating it.

The suite seeds through the port itself (``put_object``), so it makes no
assumption about how an adapter stores bytes.
"""

from abc import ABC, abstractmethod
from queue import Queue

import pytest
from naas_abi_core.services.object_storage.ObjectStoragePort import (
    Exceptions,
    IObjectStorageAdapter,
)


class ObjectStorageSecondaryAdapterContract(ABC):
    @pytest.fixture
    @abstractmethod
    def adapter(self) -> IObjectStorageAdapter:
        raise NotImplementedError()

    # -- helpers ---------------------------------------------------------

    @staticmethod
    def _seed_tree(adapter: IObjectStorageAdapter, prefix: str = "papers") -> None:
        """A subtree three levels deep, with siblings at every level."""
        adapter.put_object(prefix, "root.pdf", b"root")
        adapter.put_object(prefix, "2024/spring.pdf", b"spring")
        adapter.put_object(prefix, "2024/q1/january.pdf", b"january")
        adapter.put_object(prefix, "2024/q1/february.pdf", b"february")
        adapter.put_object(prefix, "2025/summer.pdf", b"summer")

    @staticmethod
    def _basenames(keys: list[str]) -> set[str]:
        return {key.rsplit("/", 1)[-1] for key in keys}

    # -- recursive listing ------------------------------------------------

    def test_recursive_listing_returns_objects_at_every_depth(
        self, adapter: IObjectStorageAdapter
    ):
        self._seed_tree(adapter)

        found = adapter.list_objects_recursive("papers")

        assert self._basenames(found) == {
            "root.pdf",
            "spring.pdf",
            "january.pdf",
            "february.pdf",
            "summer.pdf",
        }

    def test_recursive_listing_returns_no_directory_entries(
        self, adapter: IObjectStorageAdapter
    ):
        self._seed_tree(adapter)

        found = adapter.list_objects_recursive("papers")

        assert len(found) == 5
        for key in found:
            assert not key.endswith("/"), f"{key!r} looks like a directory entry"
        assert self._basenames(found).isdisjoint({"2024", "2025", "q1"})

    def test_recursive_and_non_recursive_agree_on_whether_a_prefix_exists(
        self, adapter: IObjectStorageAdapter
    ):
        # Stores disagree on whether a prefix with nothing under it exists at
        # all: a filesystem keeps the directory, an object store does not
        # represent one. The contract is only that the two listings agree.
        adapter.put_object("emptied", "placeholder", b"x")
        adapter.delete_object("emptied", "placeholder")

        def outcome(call):
            try:
                return ("ok", call("emptied"))
            except Exceptions.ObjectNotFound:
                return ("not_found", None)

        assert outcome(adapter.list_objects_recursive)[0] == (
            outcome(adapter.list_objects)[0]
        )

    def test_recursive_listing_of_a_missing_prefix_raises_object_not_found(
        self, adapter: IObjectStorageAdapter
    ):
        with pytest.raises(Exceptions.ObjectNotFound):
            adapter.list_objects_recursive("no/such/prefix")

    def test_recursive_listing_spans_more_than_one_provider_page(
        self, adapter: IObjectStorageAdapter
    ):
        # Comfortably more than a single S3 list_objects_v2 page would be in a
        # constrained test double, and enough to catch a truncated walk.
        expected = set()
        for index in range(120):
            key = f"batch/{index // 10}/object-{index}.txt"
            adapter.put_object("bulk", key, str(index).encode())
            expected.add(f"object-{index}.txt")

        found = adapter.list_objects_recursive("bulk")

        assert self._basenames(found) == expected

    def test_recursive_listing_feeds_the_queue_when_given_one(
        self, adapter: IObjectStorageAdapter
    ):
        self._seed_tree(adapter)
        queue: Queue = Queue()

        found = adapter.list_objects_recursive("papers", queue)

        drained = []
        while not queue.empty():
            drained.append(queue.get())
        assert sorted(drained) == sorted(found)

    # -- the existing depth-1 listing must not change ---------------------

    def test_non_recursive_listing_still_returns_direct_children_only(
        self, adapter: IObjectStorageAdapter
    ):
        self._seed_tree(adapter)

        shallow = adapter.list_objects("papers")

        assert "root.pdf" in self._basenames(shallow)
        assert self._basenames(shallow).isdisjoint(
            {"spring.pdf", "january.pdf", "february.pdf", "summer.pdf"}
        )

    def test_recursive_and_non_recursive_agree_on_a_flat_prefix(
        self, adapter: IObjectStorageAdapter
    ):
        adapter.put_object("flat", "a.txt", b"a")
        adapter.put_object("flat", "b.txt", b"b")

        assert sorted(adapter.list_objects_recursive("flat")) == sorted(
            adapter.list_objects("flat")
        )
