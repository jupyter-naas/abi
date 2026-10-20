"""Persistent per-object icon overrides. Concurrent edits are atomic; last edit wins."""
from hashlib import sha256

from naas_abi.apps.nexus.apps.api.app.models import OntologyIconModel, _utcnow
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert


class OntologyIconsPostgres:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    async def list_icons(self, workspace_id: str) -> list[dict]:
        async with self.session_factory() as db:
            result = await db.execute(select(OntologyIconModel).where(
                OntologyIconModel.workspace_id == workspace_id))
            return [{"kind": row.resource_kind, "resource_id": row.resource_id,
                     "icon": row.icon_name} for row in result.scalars()]

    async def save_icon(
        self, workspace_id: str, kind: str, resource_id: str,
        icon: str | None, user_id: str,
    ) -> None:
        # Bound the database index size independently of the resource IRI length.
        key = sha256((kind + "\0" + resource_id).encode()).hexdigest()
        async with self.session_factory() as db:
            if icon is None:
                await db.execute(delete(OntologyIconModel).where(
                    OntologyIconModel.workspace_id == workspace_id,
                    OntologyIconModel.target_key == key))
            else:
                insert = sqlite_insert if db.bind.dialect.name == "sqlite" else pg_insert
                statement = insert(OntologyIconModel).values(
                    workspace_id=workspace_id, target_key=key, resource_kind=kind,
                    resource_id=resource_id, icon_name=icon, updated_by=user_id, updated_at=_utcnow())
                await db.execute(statement.on_conflict_do_update(
                    index_elements=["workspace_id", "target_key"],
                    set_={"icon_name": icon, "updated_by": user_id, "updated_at": _utcnow()}))
            await db.commit()
