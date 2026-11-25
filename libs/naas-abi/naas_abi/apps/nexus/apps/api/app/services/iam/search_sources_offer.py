"""Search sources move into the offer, once (``search_sources_offer_v1``).

Settings › Search kept which sources a workspace switched off in ``search_settings``
(``disabled_scopes``), applied by the web page only. The sources are now a section of
the workspace's offer (``OfferSearchSources`` of "<W> access", ``workspace_offer``):
the level policies grant every source by type, the offer names which, and the API
checks ``UseSearchSource``.

This writes the section into each access policy Nexus recorded
(``container_defaults``):

* an organization's ("<O> access", the bound of its workspaces): every source;
* a workspace's: every source but those its search settings switched off.

Every other statement is kept as it is (``with_offer``), whatever the document's form.
Recorded in ``iam_migrations`` once nothing failed, so a workspace whose offer later
names no source is not given them back. As ``api``.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    is_org_container,
    is_workspace_container,
    workspace_of,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_offer import (
    SEARCH_SOURCES_SID,
    offer_of,
    offer_section,
    with_offer,
)
from naas_abi.apps.nexus.apps.api.app.services.search.sources import default_sources
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam.IAMPorts import IAMNotFoundError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

MIGRATION_NAME = "search_sources_offer_v1"
_MARKER_TABLE = (
    "CREATE TABLE IF NOT EXISTS iam_migrations ("
    "name VARCHAR(128) PRIMARY KEY, "
    "applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, "
    "report TEXT)"
)


@dataclass
class Report:
    written: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"written": len(self.written), "kept": len(self.kept), "failed": self.failed}


def has_sources_section(document: Any) -> bool:
    statements = (
        document.get("statements")
        if isinstance(document, Mapping)
        else getattr(document, "statements", ())
    )
    return any(
        offer_section(s.get("sid") if isinstance(s, Mapping) else s.sid) == SEARCH_SOURCES_SID
        for s in statements or ()
    )


def with_sources(document: Any, sources: Iterable[str]) -> dict[str, Any]:
    """``document`` with its sources section set to ``sources``; nothing else changes."""
    return with_offer(document, replace(offer_of(document), search_sources=frozenset(sources)))


def sources_for(container: str, switched_off: Mapping[str, Iterable[str]]) -> frozenset[str]:
    """Every source for an organization; a workspace's, but those it switched off
    (the defaults when it never chose)."""
    if is_workspace_container(container):
        return default_sources(switched_off.get(workspace_of(container) or ""))
    return default_sources(())


def apply(
    iam: Any, policies: Mapping[str, str], switched_off: Mapping[str, Iterable[str]]
) -> Report:
    """Write the section into each ``{container: access policy id}`` that has none.
    As ``api``."""
    report = Report()
    with as_service_account("api"):
        for container, policy_id in sorted(policies.items()):
            try:
                policy = iam.get_policy(policy_id)
            except IAMNotFoundError:
                report.kept.append(container)
                continue
            if has_sources_section(policy.document):
                report.kept.append(container)
                continue
            try:
                iam.update_policy(
                    policy.id,
                    expected_revision=policy.revision,
                    document=with_sources(policy.document, sources_for(container, switched_off)),
                )
                report.written.append(container)
            except Exception as exc:  # noqa: BLE001 - reported, retried at the next start
                report.failed[container] = str(exc)
    return report


async def _recorded(db: AsyncSession) -> bool:
    await db.execute(text(_MARKER_TABLE))
    found = await db.execute(
        text("SELECT 1 FROM iam_migrations WHERE name = :n"), {"n": MIGRATION_NAME}
    )
    return found.first() is not None


async def _switched_off(db: AsyncSession) -> dict[str, list[str]]:
    rows = (await db.execute(text("SELECT workspace_id, settings FROM search_settings"))).all()
    found: dict[str, list[str]] = {}
    for workspace_id, raw in rows:
        try:
            disabled = json.loads(raw or "{}").get("disabled_scopes") or []
        except (TypeError, ValueError, AttributeError):
            disabled = []
        found[str(workspace_id)] = [str(s) for s in disabled]
    return found


async def migrate(db: AsyncSession, iam: Any) -> Report | None:
    """Once: the sources section in every recorded access policy. None when it was
    recorded already."""
    if await _recorded(db):
        return None
    rows = (
        await db.execute(
            text(
                "SELECT container, access_policy_id FROM container_defaults "
                "WHERE access_policy_id IS NOT NULL"
            )
        )
    ).all()
    policies = {
        str(c): str(p)
        for c, p in rows
        if is_org_container(str(c)) or is_workspace_container(str(c))
    }
    switched_off = await _switched_off(db)
    report = await run_in_threadpool(apply, iam, policies, switched_off)
    if report.failed:
        logger.warning(
            "Search sources: %d access policies not written yet (next start): %s",
            len(report.failed),
            report.failed,
        )
        return report
    try:
        await db.execute(
            text("INSERT INTO iam_migrations (name, applied_at, report) VALUES (:n, :at, :r)"),
            {
                "n": MIGRATION_NAME,
                "at": datetime.now(UTC).replace(tzinfo=None),
                "r": json.dumps(report.to_dict()),
            },
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()  # another process recorded it first
    if report.written:
        from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ

        AUTHZ.forget_offers()
    logger.info("Search sources in the offer: %s", report.to_dict())
    return report
