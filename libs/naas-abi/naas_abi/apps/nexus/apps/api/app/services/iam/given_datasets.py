"""The dataset namespaces a workspace does not use: the Datasets part of its offer (ADR
``20261125_offer_gives_outside_resources``, "Datasets").

A dataset namespace belongs to no workspace: the engine's dataset service is global and
the deployment shares some namespaces (``shared_dataset_namespaces``) with every
workspace whose people hold the ``datasets`` feature (``iam/catalog/datasets.py``).
Which of them a workspace uses is its offer "<W> access" (or, for every workspace of an
organization, "<O> access"): every shared namespace unless it closes it.

| Section | Effect | Actions | Resources |
|---|---|---|---|
| ``OfferDatasetsDeny`` (parts ``OfferDatasetsDeny2``...) | Deny | ``ListDatasets``, ``GetDataset``, ``PreviewDataset``, ``QueryDataset`` | ``${scope}/nexus:dataset/<namespace>``: a namespace the workspace does not use |

A policy a container owns names only ``${scope}`` (``policy.check_owned_document``), and
IAM decides a dataset on its platform name (``abi:nexus:dataset/<namespace>``): the Deny
records the choice, and Nexus applies it (``datasets/access.py`` reads the offer of the
workspace and of its organization, and leaves a closed namespace out of every listing,
description, preview and query). Pure: no IAM, no database.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from urllib.parse import unquote

from naas_abi.apps.nexus.apps.api.app.services.iam.names import SERVICE, scoped_resource
from naas_abi_core.services.iam.policy import MAX_PATTERNS

DENY_SID = "OfferDatasetsDeny"
SIDS = (DENY_SID,)
DENY_SIDS = frozenset(SIDS)
# What a closed namespace takes away: everything Nexus does with a dataset.
ACTIONS = (
    f"{SERVICE}:ListDatasets",
    f"{SERVICE}:GetDataset",
    f"{SERVICE}:PreviewDataset",
    f"{SERVICE}:QueryDataset",
)
# The ``Offer`` field: the namespaces closed.
FIELDS = ("datasets_closed",)

_PREFIX = "${scope}/" + f"{SERVICE}:dataset/"
# As the dataset service accepts them (``DatasetsService._require_identifier``).
MAX_NAMESPACE_LENGTH = 128


def valid_namespace(namespace: str) -> bool:
    """A namespace a closure may name: no path, no wildcard, no blank."""
    return (
        bool(namespace)
        and namespace == namespace.strip()
        and len(namespace) <= MAX_NAMESPACE_LENGTH
        and not any(c in namespace for c in "/*?")
    )


def closed_name(namespace: str) -> str:
    """A namespace the workspace closes, as its offer names it."""
    return scoped_resource("dataset", namespace)


def namespace_of(name: str) -> str | None:
    """The namespace a closed name stands for; None for any other name."""
    if not name.startswith(_PREFIX):
        return None
    namespace = unquote(name[len(_PREFIX) :])
    return namespace if valid_namespace(namespace) else None


def statements(closed: Iterable[str]) -> list[dict[str, Any]]:
    """The Deny naming each closed namespace, in parts past ``MAX_PATTERNS``."""
    resources = [closed_name(ns) for ns in sorted(set(closed))]
    return [
        {
            "sid": f"{DENY_SID}{start // MAX_PATTERNS + 1}" if start else DENY_SID,
            "effect": "Deny",
            "actions": list(ACTIONS),
            "resources": resources[start : start + MAX_PATTERNS],
        }
        for start in range(0, len(resources), MAX_PATTERNS)
    ]


def closed_of(resources: Iterable[str]) -> set[str]:
    """The namespaces a Deny of the section names."""
    return {ns for r in resources if (ns := namespace_of(r)) is not None}


__all__ = [
    "ACTIONS",
    "DENY_SID",
    "DENY_SIDS",
    "FIELDS",
    "MAX_NAMESPACE_LENGTH",
    "SIDS",
    "closed_name",
    "closed_of",
    "namespace_of",
    "statements",
    "valid_namespace",
]
