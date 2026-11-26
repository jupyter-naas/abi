"""Every model, in each offer, once (``models_offer_v1``; ADR
``20261126_models_in_the_offer``).

The chat models a workspace uses are a section of its offer (``OfferModels`` of "<W>
access", ``workspace_offer``): the levels that chat grant every model by type, the
offer names which, and Nexus keeps a turn to them (``workspace_models``). Before, every
workspace used every model its people's model sets allow; so does each offer this move
writes: ``*`` into every access policy Nexus recorded (``container_defaults``), an
organization's ("<O> access", the parent of its workspaces' offers) and a workspace's.
One that names models already (chosen since) is kept.

Every other statement is kept as it is (``with_offer``). Recorded in ``iam_migrations``
once nothing failed, so a workspace limited later is never given every model back. As
``api``.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.iam import offer_moves
from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_offer import (
    EVERY_MODEL,
    MODELS_SID,
    offer_of,
    offer_section,
    with_offer,
)
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam.IAMPorts import IAMNotFoundError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

MIGRATION_NAME = "models_offer_v1"


@dataclass
class Report:
    written: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"written": len(self.written), "kept": len(self.kept), "failed": self.failed}


def has_models_section(document: Any) -> bool:
    statements = (
        document.get("statements")
        if isinstance(document, Mapping)
        else getattr(document, "statements", ())
    )
    return any(
        offer_section(s.get("sid") if isinstance(s, Mapping) else s.sid) == MODELS_SID
        for s in statements or ()
    )


def with_every_model(document: Any) -> dict[str, Any]:
    """``document`` with every model; nothing else changes."""
    return with_offer(document, replace(offer_of(document), models=frozenset({EVERY_MODEL})))


def apply(iam: Any, policies: Mapping[str, str]) -> Report:
    """Every model in each ``{container: access policy id}`` that names none. As ``api``."""
    report = Report()
    with as_service_account("api"):
        for container, policy_id in sorted(policies.items()):
            try:
                policy = iam.get_policy(policy_id)
            except IAMNotFoundError:
                report.kept.append(container)
                continue
            if has_models_section(policy.document):
                report.kept.append(container)
                continue
            try:
                iam.update_policy(
                    policy.id,
                    expected_revision=policy.revision,
                    document=with_every_model(policy.document),
                )
                report.written.append(container)
            except Exception as exc:  # noqa: BLE001 - reported, retried at the next start
                report.failed[container] = str(exc)
    return report


async def migrate(db: AsyncSession, iam: Any) -> Report | None:
    """Once: every model in every recorded access policy. None when recorded."""
    if await offer_moves.recorded(db, MIGRATION_NAME):
        return None
    policies = await offer_moves.access_policies(db)
    report = await run_in_threadpool(apply, iam, policies)
    if report.failed:
        logger.warning(
            "Models: %d access policies not written yet (next start): %s",
            len(report.failed),
            report.failed,
        )
        return report
    await offer_moves.record(db, MIGRATION_NAME, report.to_dict())
    if report.written:
        from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ

        AUTHZ.forget_offers()
    logger.info("Models in the offer: %s", report.to_dict())
    return report


__all__ = ["MIGRATION_NAME", "Report", "apply", "has_models_section", "migrate"]
