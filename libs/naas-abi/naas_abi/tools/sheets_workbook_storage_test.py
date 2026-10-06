from naas_abi.tools.sheets_workbook_storage import (
    branch_name,
    workbook_path,
)


def test_workbook_paths_are_namespaced_under_sheets() -> None:
    assert (
        workbook_path("budget-q1", "ws-abc") == "sheets/ws-abc/budget-q1/workbook.html"
    )
    assert branch_name("budget-q1", "ws-abc") == "sheets/ws-abc/budget-q1"


def test_viewer_agent_cannot_persist(monkeypatch):
    from naas_abi_core.services.agent.context import agent_user_id, agent_workspace_id

    from naas_abi.agents.feature import runtime
    from naas_abi.tools import sheets_workbook_storage as store

    user = agent_user_id.set("viewer")
    workspace = agent_workspace_id.set("ws-test")
    monkeypatch.setattr(runtime, "check_member", lambda *args: "viewer")

    def unexpected(*args, **kwargs):
        raise AssertionError("must not reach storage")

    monkeypatch.setattr(store, "get_source_control", unexpected)
    try:
        result = store.persist_workbook(
            "demo", "changed", "edit"
        )
        assert "writer role" in result["error"]
    finally:
        agent_user_id.reset(user)
        agent_workspace_id.reset(workspace)
