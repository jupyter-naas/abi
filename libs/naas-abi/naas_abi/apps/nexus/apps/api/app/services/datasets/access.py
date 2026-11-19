"""Who may reach which dataset, decided as the routes decide it, for every caller of
the datasets (the routes and the agents' tools).

A dataset is ``dataset/<namespace>/<name>`` and its namespace ``dataset/<namespace>``
(platform-wide, ``iam/catalog/datasets.py``); the workspace a call names carries the
``datasets`` feature and the caller's membership. A Deny on either name hides the
dataset: a listing leaves it out, and a query refuses SQL that reads it through any
namespace, not only the one it is sent to. The kernel reads a name as spelled or in
lower case (``DatasetService``), so both spellings are checked.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any, TypeVar

from naas_abi.apps.nexus.apps.api.app.services.datasets.datasets__schema import (
    DatasetQueryError,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ
from naas_abi.apps.nexus.apps.api.app.services.iam.names import nexus_resource
from naas_abi_core.services.dataset.DatasetPort import DatasetRequestRefused
from naas_abi_core.services.dataset.sql_references import referenced_datasets

_T = TypeVar("_T")


def referenced(sql: str, namespace: str) -> list[tuple[str, str]]:
    """The ``(namespace, name)`` datasets ``sql`` reads, unqualified names in
    ``namespace``. SQL whose datasets cannot be named is refused."""
    try:
        return referenced_datasets(sql, namespace)
    except DatasetRequestRefused as exc:
        raise DatasetQueryError(str(exc)) from exc


async def require_datasets(
    action: str,
    datasets: Sequence[tuple[str, str]],
    *,
    user: Any,
    workspace_id: str,
    namespaces: Iterable[str] = (),
) -> None:
    """``action`` on each dataset and on each one's namespace (and on ``namespaces``),
    in ``workspace_id``, under every spelling the kernel may read them by:
    ``AuthzDenied`` for the first refused."""
    spelled = list(dict.fromkeys(_spellings(datasets)))
    names = list(
        dict.fromkeys(
            [*(s for ns in namespaces for s in (ns, ns.lower())), *(ns for ns, _ in spelled)]
        )
    )
    for namespace in names:
        await AUTHZ.require(action, user=user, workspace=workspace_id, id=namespace)
    for namespace, name in spelled:
        await AUTHZ.require(action, user=user, workspace=workspace_id, id=[namespace, name])


def _spellings(datasets: Sequence[tuple[str, str]]) -> list[tuple[str, str]]:
    """Each ``(namespace, name)`` as the kernel may read it: as spelled and in lower
    case, each part."""
    return [
        (ns, n)
        for namespace, name in datasets
        for ns in (namespace, namespace.lower())
        for n in (name, name.lower())
    ]


async def require_query(user: Any, workspace_id: str, sql: str, namespace: str) -> None:
    """``QueryDataset`` on the namespace a query is sent to and on every dataset, and
    its namespace, that its SQL reads."""
    await require_datasets(
        "QueryDataset",
        referenced(sql, namespace),
        user=user,
        workspace_id=workspace_id,
        namespaces=(namespace,),
    )


async def visible(items: Iterable[_T], *, user: Any) -> list[_T]:
    """The datasets (``.namespace``, ``.name``) the user may list, and whose
    namespace they may list."""
    kept = await AUTHZ.filter(
        "ListDatasets",
        items,
        user=user,
        resource_of=lambda item: nexus_resource("dataset", id=[item.namespace, item.name]),
    )
    namespaces = sorted({item.namespace for item in kept})
    allowed = set(
        await AUTHZ.filter(
            "ListDatasets",
            namespaces,
            user=user,
            resource_of=lambda one: nexus_resource("dataset", id=one),
        )
    )
    return [item for item in kept if item.namespace in allowed]


__all__ = ["referenced", "require_datasets", "require_query", "visible"]
