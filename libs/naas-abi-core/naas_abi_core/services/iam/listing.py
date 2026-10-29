"""Listing the existing resources of a type, as the caller (``AGENTS.md``,
"Publishers and listing").

A lister finds candidates: the resources of one type in a container, by
canonical name, sorted, a page at a time. It decides nothing. ``run_listing``
reads it page by page and keeps what the caller may list (``filter`` with the
type's ``list`` actions, else any of its actions), within the scope, matching
the search text, after the cursor. A lister that fails leaves the type offered
as wildcards only, and is logged.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, replace

from naas_abi_core import logger
from naas_abi_core.services.iam.names import (
    PLATFORM,
    container_of_scope,
    parse_resource_name,
    validate_scope,
    within,
)

# A page of a listing, by default and at most.
DEFAULT_LIMIT = 50
MAX_LIMIT = 200
# The candidates one call examines at most: past it, the page is short and has
# a cursor, so a caller who may list few of many still gets an answer.
MAX_EXAMINED = 5000
# What one call asks a lister for at a time.
BATCH = 200
# The longest search text.
MAX_TEXT = 200


@dataclass(frozen=True)
class ListedResource:
    """An existing resource: its canonical name, its decoded id, and what a
    person reads (``label``, ``description``), when the lister knows it."""

    name: str
    id: str
    label: str = ""
    description: str = ""


@dataclass(frozen=True)
class ListingQuery:
    """What a lister is asked: the resources of ``service:type`` in
    ``container`` (in it or below it; everything at the platform), whose id or
    label contains ``text`` when it can tell (IAM matches again), by name after
    ``after``, at most ``limit``."""

    service: str
    type: str
    container: str = PLATFORM
    text: str = ""
    after: str = ""
    limit: int = BATCH
    # The ``module`` catalog's: that module's items only (empty: every module's).
    module: str = ""


@dataclass(frozen=True)
class ListedPage:
    """A lister's answer: ``items`` sorted by name, after ``after``, at most
    ``limit``; ``more`` when there are others after the last."""

    items: tuple[ListedResource, ...]
    more: bool = False


class ResourceLister(ABC):
    """The existing resources of one type (the lister port)."""

    @abstractmethod
    def list_resources(self, query: ListingQuery) -> ListedPage:
        """Candidates for ``query``. Raise on failure: the type is then offered
        as wildcards, never refused."""


class FunctionLister(ResourceLister):
    """A lister over a function returning every candidate of a query (filtered
    by container and text here), for listers that read a whole list at once."""

    def __init__(self, items: Callable[[ListingQuery], Iterable[ListedResource]]) -> None:
        self._items = items

    def list_resources(self, query: ListingQuery) -> ListedPage:
        return page_of(self._items(query), query)


class ListerDirectory(ABC):
    """Listers found elsewhere than in process: a remote module's, over NATS."""

    @abstractmethod
    def lister(self, module: str, service: str, type: str) -> ResourceLister | None:
        """The lister ``module`` serves for ``service:type``; None when no ready
        instance of it serves one."""


@dataclass(frozen=True)
class ResourcePage:
    """A listing as the caller. ``listed`` False: the type has no lister, or
    its lister failed; it is offered as wildcards only."""

    items: tuple[ListedResource, ...] = ()
    next_cursor: str | None = None
    listed: bool = True


def matches_text(item: ListedResource, text: str) -> bool:
    if not text:
        return True
    needle = text.casefold()
    return needle in item.id.casefold() or needle in item.label.casefold()


def in_container(name: str, container: str) -> bool:
    """Whether the resource ``name`` sits in ``container`` or below it."""
    if container == PLATFORM:
        return True
    try:
        return within(parse_resource_name(name).container, container)
    except ValueError:
        return False


def page_of(items: Iterable[ListedResource], query: ListingQuery) -> ListedPage:
    """A page of ``items`` for ``query``: in its container, matching its text,
    after its name, sorted, at most its limit."""
    found = sorted(
        (
            item
            for item in items
            if item.name > query.after
            and in_container(item.name, query.container)
            and matches_text(item, query.text)
        ),
        key=lambda item: item.name,
    )
    unique = [item for i, item in enumerate(found) if i == 0 or found[i - 1].name != item.name]
    limit = max(query.limit, 1)
    return ListedPage(tuple(unique[:limit]), more=len(unique) > limit)


def listing_scope(scope: str) -> str:
    """The container a listing at ``scope`` reads: a below scope's container."""
    return container_of_scope(validate_scope(scope))


def _type_of(name: str, service: str, type: str) -> bool:
    try:
        parsed = parse_resource_name(name)
    except ValueError:
        return False
    return parsed.service == service and parsed.type == type


def run_listing(
    lister: ResourceLister,
    query: ListingQuery,
    *,
    limit: int,
    allowed: Callable[[Sequence[str]], set[str]],
    keep: Callable[[ListedResource], bool] = lambda _item: True,
) -> ResourcePage:
    """Read ``lister`` from ``query.after`` until ``limit`` resources the caller
    may list are found (``allowed``: the names of a batch they may list), at most
    ``MAX_EXAMINED`` candidates. ``keep``: a further test of each (a container's
    registry). What falls outside the query (another type, container, text, or
    out of order) is dropped. A lister that fails gives ``listed`` False."""
    found: list[ListedResource] = []
    after = query.after
    examined = 0
    while True:
        asked = replace(query, after=after, limit=BATCH)
        try:
            page = lister.list_resources(asked)
            items = tuple(page.items)
            if any(not isinstance(item, ListedResource) for item in items):
                raise TypeError("a lister returns ListedResource items")
        except Exception as exc:  # noqa: BLE001 - a lister never fails the listing
            logger.warning(
                f"Listing {query.service}:{query.type}: its lister failed, "
                f"offered as wildcards: {exc!r}"
            )
            return ResourcePage(listed=False)
        ordered = [item for item in items if item.name > after]
        ordered.sort(key=lambda item: item.name)
        candidates = [
            item
            for item in ordered
            if _type_of(item.name, query.service, query.type)
            and in_container(item.name, query.container)
            and matches_text(item, query.text)
            and keep(item)
        ]
        permitted = allowed([item.name for item in candidates]) if candidates else set()
        kept = {item.name for item in candidates if item.name in permitted}
        for item in ordered:
            examined += 1
            after = item.name
            if item.name in kept:
                found.append(item)
                kept.discard(item.name)
                if len(found) >= limit:
                    more = page.more or item is not ordered[-1]
                    return ResourcePage(tuple(found), after if more else None)
        if not page.more or not ordered:
            return ResourcePage(tuple(found), None)
        if examined >= MAX_EXAMINED:
            return ResourcePage(tuple(found), after)


def clamp_limit(limit: int | None) -> int:
    if limit is None or limit <= 0:
        return DEFAULT_LIMIT
    return min(limit, MAX_LIMIT)
