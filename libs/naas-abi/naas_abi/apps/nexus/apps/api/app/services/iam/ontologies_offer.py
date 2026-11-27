"""Ontologies move into the offer, once (``ontologies_offer_v1``).

Settings › Ontologies kept a workspace's enabled ontology files in
``workspace_resource_policies`` (``enabled``: refs such as ``module:file.ttl``), read
by the ontology routes before IAM. They are now a section of the workspace's offer
(``OfferOntologies`` of "<W> access", ``workspace_offer``): the level policies grant
every file by type (``UseOntology``), the offer names which.

This writes into each access policy Nexus recorded (``container_defaults``):

* a workspace's: its enabled refs, as Settings › Ontologies showed them (its stored
  list, else its configuration's);
* an organization's ("<O> access", the bound of its workspaces): every ontology file,
  as its admins could assign any (``AssignOntology``): ``Ontologies``, one statement
  beside the offer's sections.

Every other statement is kept. Recorded in ``iam_migrations`` once nothing failed.
As ``api``.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.iam import offer_moves
from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    is_org_container,
    is_workspace_container,
    workspace_of,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_offer import (
    ONTOLOGIES_SID,
    POLICY_VERSION,
    USE_ONTOLOGY,
    offer_of,
    offer_section,
    with_offer,
)
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam.IAMPorts import IAMNotFoundError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

MIGRATION_NAME = "ontologies_offer_v1"
# What an organization's offer allows of the ontology files: every one, by type.
EVERY_FILE_SID = "Ontologies"
EVERY_FILE = {
    "sid": EVERY_FILE_SID,
    "effect": "Allow",
    "actions": [USE_ONTOLOGY],
    "resources": ["${scope}/nexus:ontology_file/*"],
}


@dataclass
class Report:
    written: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"written": len(self.written), "kept": len(self.kept), "failed": self.failed}


def _statements(document: Any) -> list[dict[str, Any]]:
    raw = document if isinstance(document, Mapping) else document.to_dict()
    return [dict(s) for s in raw.get("statements") or []]


def has_ontologies(document: Any) -> bool:
    return any(
        s.get("sid") == EVERY_FILE_SID or offer_section(s.get("sid")) == ONTOLOGIES_SID
        for s in _statements(document)
    )


def with_ontologies(document: Any, container: str, refs: Iterable[str]) -> dict[str, Any]:
    """An organization's document with every file allowed; a workspace's with its
    refs as its ``OfferOntologies`` section. Nothing else changes."""
    if is_org_container(container):
        return {"version": POLICY_VERSION, "statements": [*_statements(document), EVERY_FILE]}
    return with_offer(document, replace(offer_of(document), ontologies=frozenset(refs)))


def apply(iam: Any, policies: Mapping[str, str], enabled: Mapping[str, Iterable[str]]) -> Report:
    """Write into each ``{container: access policy id}`` that has none yet; a
    workspace's refs are ``enabled[workspace id]``. As ``api``."""
    report = Report()
    with as_service_account("api"):
        for container, policy_id in sorted(policies.items()):
            try:
                policy = iam.get_policy(policy_id)
            except IAMNotFoundError:
                report.kept.append(container)
                continue
            if has_ontologies(policy.document):
                report.kept.append(container)
                continue
            refs = enabled.get(workspace_of(container) or "", ())
            try:
                iam.update_policy(
                    policy.id,
                    expected_revision=policy.revision,
                    document=with_ontologies(policy.document, container, refs),
                )
                report.written.append(container)
            except Exception as exc:  # noqa: BLE001 - reported, retried at the next start
                report.failed[container] = str(exc)
    return report


async def _enabled(db: AsyncSession, workspaces: Iterable[str]) -> dict[str, list[str]]:
    from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.secondary.resource_access_postgres import (  # noqa: E501
        load_resource_policy,
    )

    found: dict[str, list[str]] = {}
    for workspace_id in workspaces:
        try:
            saved = await load_resource_policy(db, workspace_id, "ontologies")
        except LookupError:
            continue
        found[workspace_id] = [str(r) for r in saved.data.get("enabled") or []]
    return found


async def migrate(db: AsyncSession, iam: Any) -> Report | None:
    """Once: the ontologies in every recorded access policy. None when recorded."""
    if await offer_moves.recorded(db, MIGRATION_NAME):
        return None
    policies = await offer_moves.access_policies(db)
    workspaces = [
        w for c in policies if is_workspace_container(c) and (w := workspace_of(c)) is not None
    ]
    enabled = await _enabled(db, workspaces)
    report = await run_in_threadpool(apply, iam, policies, enabled)
    if report.failed:
        logger.warning(
            "Ontologies: %d access policies not written yet (next start): %s",
            len(report.failed),
            report.failed,
        )
        return report
    await offer_moves.record(db, MIGRATION_NAME, report.to_dict())
    if report.written:
        from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ

        AUTHZ.forget_offers()
    logger.info("Ontologies in the offer: %s", report.to_dict())
    return report
