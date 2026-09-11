from __future__ import annotations

from types import SimpleNamespace

import pytest
from naas_abi.agents.feature.context import nexus_feature_context
from naas_abi.agents.tools import datasets_tools, files_tools, graph_tools, maps_tools
from naas_abi_core.services.agent.context import agent_user_id, agent_workspace_id


@pytest.fixture(autouse=True)
def _request_context():
    tokens = (
        agent_user_id.set("user-1"),
        agent_workspace_id.set("ws-1"),
        nexus_feature_context.set(None),
    )
    yield
    agent_user_id.reset(tokens[0])
    agent_workspace_id.reset(tokens[1])
    nexus_feature_context.reset(tokens[2])


def _open(key: str, kind: str, resource_id: str) -> None:
    nexus_feature_context.set(
        {"key": key, "resource": {"kind": kind, "id": resource_id}}
    )


# ── Knowledge Graph: only graphs the workspace lists ─────────────────────────

_GRAPHS = [
    SimpleNamespace(id="sales", uri="http://x/graph/sales", label="Sales"),
    SimpleNamespace(id="hr", uri="http://x/graph/hr", label="HR"),
]


def test_graph_resolves_by_id_uri_or_label() -> None:
    assert graph_tools._resolve_graph("sales", _GRAPHS).id == "sales"
    assert graph_tools._resolve_graph("http://x/graph/hr", _GRAPHS).id == "hr"
    assert graph_tools._resolve_graph("sales", _GRAPHS).uri == "http://x/graph/sales"
    assert graph_tools._resolve_graph("hr", _GRAPHS).label == "HR"


def test_graph_refuses_a_graph_outside_the_workspace() -> None:
    out = graph_tools._resolve_graph("http://other-tenant/graph/secret", _GRAPHS)
    assert "not in this workspace" in out["error"]


def test_graph_defaults_to_the_open_graph() -> None:
    _open("graph", "graph", "hr")
    assert graph_tools._resolve_graph("", _GRAPHS).id == "hr"


# ── Files: drive comes from the open item, never guessed wrong ───────────────


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("my_drive:notes/a.md", ("my_drive", "notes/a.md")),
        (
            "naas_abi/my-drive/user-1/a.md",
            ("my_drive", "naas_abi/my-drive/user-1/a.md"),
        ),
        ("docs/a.md", ("workspace", "docs/a.md")),
        ("", ("workspace", "")),
    ],
)
def test_files_split_drive(value: str, expected: tuple[str, str]) -> None:
    assert files_tools._split_drive(value) == expected


def test_files_scope_stays_in_the_callers_workspace() -> None:
    other = files_tools._scoped(
        "naas_abi/workspace-drive/ws-2/secret.txt", "workspace", "user-1", "ws-1"
    )
    assert "error" in other
    mine = files_tools._scoped("docs/a.md", "workspace", "user-1", "ws-1")
    assert mine == "naas_abi/workspace-drive/ws-1/docs/a.md"
    my_drive = files_tools._scoped("a.md", "my_drive", "user-1", "ws-1")
    assert my_drive == "naas_abi/my-drive/user-1/a.md"


# ── Datasets: namespace/name from the open dataset ──────────────────────────


def test_datasets_split_uses_the_open_dataset() -> None:
    assert "No dataset is open" in datasets_tools._split("")["error"]
    _open("datasets", "dataset", "sales/orders")
    assert datasets_tools._split("") == ("sales", "orders")
    assert datasets_tools._split("hr/people") == ("hr", "people")
    assert "namespace/name" in datasets_tools._split("orders")["error"]


# ── Maps: the TypeScript catalog parses ─────────────────────────────────────


def test_maps_catalog_parser() -> None:
    text = """
const MAPS_BUILTIN_DATASETS: MapsDataset[] = [
  {
    id: 'earthquakes',
    title: 'Earthquakes',
    description: 'USGS GeoJSON feed.',
    category: 'public',
  },
  {
    id: 'wildfires',
    title: 'Wildfires',
    description:
      'EONET wildfires. It\\'s optional FIRMS.',
    category: 'public',
  },
];
"""
    layers = maps_tools.parse_maps_catalog(text)
    assert [layer["id"] for layer in layers] == ["earthquakes", "wildfires"]
    assert layers[1]["description"] == "EONET wildfires. It's optional FIRMS."


def test_maps_real_catalog_has_the_builtin_layers() -> None:
    if not maps_tools.CATALOG_PATH.is_file():
        pytest.skip("web sources not shipped")
    ids = {
        layer["id"]
        for layer in maps_tools.parse_maps_catalog(maps_tools.CATALOG_PATH.read_text())
    }
    assert {"earthquakes", "wildfires", "presence"} <= ids


# ── Settings: secret values never reach the model ───────────────────────────


def test_secret_listing_returns_names_only(monkeypatch) -> None:
    from naas_abi.agents.tools import settings_tools

    secret = SimpleNamespace(
        key="OPENAI_API_KEY",
        category="ai",
        description="",
        masked_value="sk-...abcd",
        updated_at=None,
    )

    class _Service:
        def __init__(self, adapter):
            del adapter

        async def list_secrets(self, context, workspace_id):
            return [secret]

    async def _member(db, user_id, workspace_id):
        return "owner"

    monkeypatch.setattr(settings_tools, "require_member", _member)
    monkeypatch.setattr(
        settings_tools, "run_db", lambda fn: __import__("asyncio").run(fn(object()))
    )
    monkeypatch.setattr(
        "naas_abi.apps.nexus.apps.api.app.services.secrets.service.SecretsService",
        _Service,
    )
    tool = {t.name: t for t in settings_tools.settings_tools()}[
        "list_workspace_secret_names"
    ]
    out = tool.invoke({})

    assert out["secrets"][0]["key"] == "OPENAI_API_KEY"
    assert "abcd" not in str(out)
    assert "masked_value" not in str(out)


def test_member_list_marks_the_caller(monkeypatch) -> None:
    from datetime import UTC, datetime

    from naas_abi.agents.tools import nexus_admin_tools
    from naas_abi.apps.nexus.apps.api.app.services.workspaces.port import (
        WorkspaceMemberRecord,
    )

    rows = [
        WorkspaceMemberRecord(
            "m1", "ws-1", "user-1", "owner", created_at=datetime(2026, 9, 1, tzinfo=UTC)
        ),
        WorkspaceMemberRecord("m2", "ws-1", "user-2", "admin"),
    ]

    class _Workspaces:
        async def require_workspace_access(self, user_id, workspace_id):
            return "owner"

        async def list_workspace_members(self, workspace_id):
            return rows

    async def _with_db(fn):
        return await fn(object())

    monkeypatch.setattr(
        nexus_admin_tools, "_workspace_service", lambda db: _Workspaces()
    )
    monkeypatch.setattr(nexus_admin_tools, "_with_db", _with_db)
    tool = {t.name: t for t in nexus_admin_tools.nexus_admin_tools()}[
        "list_workspace_members"
    ]

    out = tool.invoke({})

    assert [(r["user_id"], r["is_you"]) for r in out] == [
        ("user-1", True),
        ("user-2", False),
    ]
