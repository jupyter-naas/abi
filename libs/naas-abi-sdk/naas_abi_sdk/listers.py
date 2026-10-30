"""A module's listers: the existing resources of its declared catalog's types.

The policy builder lists what exists of each resource type (core
``services/iam/AGENTS.md``, "Publishers and listing"). For a type of a remote
module's catalog, IAM asks the module: a lister registered with ``@lister`` (or
``BaseModule.expose_lister``) is served on
``abi.mod.<project>.<sa>.<instance>.iam.list`` and its type is named in the
module's discovery descriptor (``ModuleDescriptor.listers``).

A lister returns candidates: the resources of its type in the container asked
(in it or below it), as canonical names. IAM keeps what the caller may list. No
action names the subject, so the broker lets only the engine's own connections
publish there: the module answers as itself. Keep this importable without
``nats`` (stdlib and proto only).
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from naas_abi_proto.discovery.v1 import discovery_pb2 as pb

logger = logging.getLogger(__name__)

# The attribute ``@lister`` sets on a method: the resource type it lists.
LISTER_ATTR = "__abi_lister__"
MAX_ITEMS = 500
MAX_REQUEST_BYTES = 16 * 1024


@dataclass(frozen=True)
class Listed:
    """A resource a lister returns: its canonical name (``resource_name`` of
    the module's catalog in a container), its id, and what a person reads."""

    name: str
    id: str
    label: str = ""
    description: str = ""


@dataclass(frozen=True)
class ListerQuery:
    """What IAM asks: the resources of ``service:type`` in ``container`` (in it
    or below it; everything at ``abi:``) whose id or label contains ``text``."""

    service: str
    type: str
    container: str
    text: str = ""


ListerHandler = Callable[[ListerQuery], "Awaitable[Iterable[Listed]] | Iterable[Listed]"]


def lister(type_name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Mark a module method ``(self, query: ListerQuery) -> Iterable[Listed]``
    (sync or async) as the lister of ``type_name``, a type of its catalog."""

    def mark(method: Callable[..., Any]) -> Callable[..., Any]:
        setattr(method, LISTER_ATTR, type_name)
        return method

    return mark


def declared_listers(module: Any) -> dict[str, Callable[..., Any]]:
    """The listers of ``module`` (a module class or instance), by type:
    ``@lister`` methods (bound for an instance), then those it exposed."""
    cls = module if isinstance(module, type) else type(module)
    found: dict[str, Callable[..., Any]] = {}
    for klass in reversed(cls.__mro__):
        for name, member in vars(klass).items():
            type_name = getattr(member, LISTER_ATTR, None)
            if isinstance(type_name, str):
                found[type_name] = (
                    member if isinstance(module, type) else getattr(module, name)
                )
    if not isinstance(module, type):
        found.update(module.__dict__.get("_lister_handlers", {}))
    return found


def check_listers(types: Iterable[str], catalog: Mapping[str, Any] | None) -> None:
    """Every listed type is a resource type of the module's declared catalog."""
    declared = {
        str(t.get("name"))
        for t in (catalog or {}).get("resource_types") or ()
        if isinstance(t, Mapping)
    }
    unknown = sorted(set(types) - declared)
    if unknown:
        raise ValueError(
            f"Listers of types the module's catalog does not declare: {unknown}"
        )


def lister_subject(project: str, service_account: str, instance_id: str) -> str:
    return f"abi.mod.{project}.{service_account or '-'}.{instance_id}.iam.list"


def _matches(item: Listed, query: pb.ListerQuery) -> bool:
    if item.name <= query.after:
        return False
    text = query.text.casefold()
    return not text or text in item.id.casefold() or text in item.label.casefold()


def _within(name: str, container: str) -> bool:
    if container in ("", "abi:"):
        return True
    return name.startswith(container + "/")


def page(items: Iterable[Listed], query: pb.ListerQuery) -> pb.ListerPage:
    """A page of ``items`` for ``query``: in its container, matching its text,
    after its name, sorted, at most its limit."""
    found = sorted(
        {
            item.name: item
            for item in items
            if _matches(item, query) and _within(item.name, query.container)
        }.values(),
        key=lambda item: item.name,
    )
    limit = min(query.limit or MAX_ITEMS, MAX_ITEMS)
    return pb.ListerPage(
        items=[
            pb.ListedResource(
                name=i.name, id=i.id, label=i.label, description=i.description
            )
            for i in found[:limit]
        ],
        more=len(found) > limit,
    )


async def run_lister(
    handlers: Mapping[str, Callable[..., Any]], service: str, query: pb.ListerQuery
) -> pb.ListerPage:
    """Answer ``query`` with the lister of its type; an error page otherwise."""
    handler = handlers.get(query.type)
    if query.service != service or handler is None:
        return pb.ListerPage(
            error={
                "code": "NOT_FOUND",
                "message": f"No lister for {query.service}:{query.type}",
            }
        )
    try:
        result = handler(
            ListerQuery(query.service, query.type, query.container, query.text)
        )
        if inspect.isawaitable(result):
            result = await result
        items = list(result)
        if any(not isinstance(item, Listed) for item in items):
            raise TypeError("a lister returns Listed items")
        return page(items, query)
    except Exception:
        logger.exception("Lister of %s:%s failed", query.service, query.type)
        return pb.ListerPage(
            error={"code": "LISTER_ERROR", "message": "The lister failed"}
        )


async def call_lister(
    transport: Any,
    project: str,
    instance_id: str,
    query: pb.ListerQuery,
    *,
    service_account: str,
) -> pb.ListerPage:
    """Ask one instance's lister (the engine does, for IAM)."""
    return await transport.call(
        lister_subject(project, service_account, instance_id), query, pb.ListerPage
    )


class ListerHost:
    """Serves a module's listers on its instance's subject."""

    def __init__(
        self,
        session: Any,
        service: str,
        handlers: Mapping[str, Callable[..., Any]],
    ) -> None:
        self.session, self.service, self.handlers = session, service, dict(handlers)
        self.subscription: Any = None

    async def start(self) -> None:
        from naas_abi_sdk.broker_flush import flush_to_broker

        nc = await self.session.client.transport.connect()
        self.subscription = await nc.subscribe(
            lister_subject(
                self.session.client.project,
                self.session.service_account,
                self.session.instance_id,
            ),
            cb=self._handle,
        )
        await flush_to_broker(nc)

    async def close(self) -> None:
        if self.subscription is not None:
            await self.subscription.unsubscribe()
            self.subscription = None

    async def _handle(self, msg: Any) -> None:
        from naas_abi_sdk.messages import reply

        if len(msg.data) > MAX_REQUEST_BYTES:
            response = pb.ListerPage(
                error={"code": "PAYLOAD_TOO_LARGE", "message": "Lister query too large"}
            )
        else:
            try:
                query = pb.ListerQuery.FromString(msg.data)
            except Exception:  # noqa: BLE001 - a malformed query is answered as one
                response = pb.ListerPage(
                    error={"code": "INVALID_ARGUMENT", "message": "Malformed query"}
                )
            else:
                response = await run_lister(self.handlers, self.service, query)
        if msg.reply:
            await reply(msg, response.SerializeToString())
