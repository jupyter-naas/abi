from naas_abi_core.engine.call_context import current_call_context
from naas_abi_core.services.event import local_identity

from naas_abi_cli.cli.local_operator import as_local_operator


def test_terminal_work_runs_as_the_engine_for_its_git_author(monkeypatch):
    monkeypatch.setattr(local_identity, "git_user_email", lambda: "Ada@Example.com")
    with as_local_operator():
        context = current_call_context()
        assert context.principal.name == "engine"
        assert context.user is not None
        assert context.user.id == local_identity.email_actor_id("ada@example.com")
        assert context.triggered_via == "cli"
    assert current_call_context().principal.kind == "anonymous"


def test_without_a_git_author_it_runs_as_the_engine_for_nobody(monkeypatch):
    monkeypatch.setattr(local_identity, "git_user_email", lambda: None)
    with as_local_operator():
        context = current_call_context()
        assert context.principal.name == "engine" and context.user is None
