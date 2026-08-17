import os

from naas_abi_core.services.gatekeeper.adapters.secondary.GatekeeperSqliteAdapter import (
    GatekeeperSqliteAdapter,
)
from naas_abi_core.services.gatekeeper.GatekeeperService import GatekeeperService


class GatekeeperFactory:
    @staticmethod
    def GatekeeperServiceSqlite(
        data_dir: str = "storage/gatekeeper",
        db_name: str = "gatekeeper.sqlite",
    ) -> GatekeeperService:
        os.makedirs(data_dir, exist_ok=True)
        adapter = GatekeeperSqliteAdapter(db_path=os.path.join(data_dir, db_name))
        return GatekeeperService(
            observation_store=adapter,
            grant_store=adapter,
        )
