from datetime import UTC, datetime

from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig, settings
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.primary.workspaces__primary_adapter__FastAPI import (
    _to_schema,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.port import WorkspaceRecord


def test_to_schema_includes_role_and_feature_flags_for_member() -> None:
    previous_config = settings.feature_flags
    settings.feature_flags = FeatureFlagsConfig(
        workspace_overrides={
            "demo": {
                "knowledge": True,
            }
        }
    )
    try:
        record = WorkspaceRecord(
            id="ws-1",
            name="Demo",
            slug="demo",
            owner_id="user-1",
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )

        schema = _to_schema(record, "member")

        assert schema.current_user_role == "member"
        assert schema.feature_flags == {
            "chat": True,
            "files": True,
            "agents": False,
            "knowledge": True,
            "settings": False,
        }
    finally:
        settings.feature_flags = previous_config
