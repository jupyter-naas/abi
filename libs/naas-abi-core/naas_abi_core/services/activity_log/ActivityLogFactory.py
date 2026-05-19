from naas_abi_core.services.activity_log.ActivityLogService import ActivityLogService
from naas_abi_core.services.activity_log.adapters.secondary.ActivityLogSqliteAdapter import (
    ActivityLogSqliteAdapter,
)


class ActivityLogFactory:
    @staticmethod
    def ActivityLogServiceSqlite(
        data_dir: str,
        synchronous: str = "NORMAL",
        journal_mode: str = "WAL",
        max_open_connections: int = 200,
        busy_timeout_ms: int = 5000,
    ) -> ActivityLogService:
        return ActivityLogService(
            ActivityLogSqliteAdapter(
                data_dir=data_dir,
                synchronous=synchronous,  # type: ignore[arg-type]
                journal_mode=journal_mode,  # type: ignore[arg-type]
                max_open_connections=max_open_connections,
                busy_timeout_ms=busy_timeout_ms,
            )
        )
