from datetime import UTC, datetime

from naas_abi.apps.nexus.apps.api.app.core.feature_flags import KNOWN_FEATURE_KEYS
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.primary.workspaces__primary_adapter__FastAPI import (
    _to_schema,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.port import WorkspaceRecord


def test_to_schema_shows_iams_flags_and_none_without_them() -> None:
    record = WorkspaceRecord(
        id="ws-1",
        name="Demo",
        slug="demo",
        owner_id="user-1",
        created_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC),
    )

    schema = _to_schema(record, "owner")

    assert schema.current_user_role == "owner"
    # No role brings a feature: without IAM's answer, none is shown, an owner's included.
    assert schema.feature_flags == dict.fromkeys(KNOWN_FEATURE_KEYS, False)
    flags = {**schema.feature_flags, "apps": True}
    assert _to_schema(record, "member", feature_flags=flags).feature_flags == flags
