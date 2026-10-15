import os

from naas_abi_core.services.bus.BusService import BusService
from naas_abi_core.services.event.adapters.secondary.EventSQLiteAdapter import (
    EventSQLiteAdapter,
)
from naas_abi_core.services.event.EventService import EventService
from naas_abi_core.utils.Storage import NoStorageFolderFound, find_storage_folder


class EventFactory:
    @staticmethod
    def EventSQLite_find_storage(
        bus: BusService | None = None,
        subpath: str = "events.sqlite",
        needle: str = "storage",
    ) -> EventService:
        try:
            root = find_storage_folder(os.getcwd(), needle)
        except NoStorageFolderFound:
            os.makedirs(os.path.join(os.getcwd(), "storage"), exist_ok=True)
            root = find_storage_folder(os.getcwd(), needle)

        if not subpath.startswith("events"):
            subpath = os.path.join("events", subpath)

        db_path = os.path.join(root, subpath)
        return EventService(adapter=EventSQLiteAdapter(db_path), bus=bus)

    @staticmethod
    def EventServicePostgreSQL(
        dsn: str, schema: str = "abi_event", bus: BusService | None = None
    ) -> EventService:
        """An event log every engine shares (deploys without downtime)."""
        from naas_abi_core.services.event.adapters.secondary.EventPostgreSQLAdapter import (
            EventPostgreSQLAdapter,
        )

        return EventService(adapter=EventPostgreSQLAdapter(dsn, schema=schema), bus=bus)
