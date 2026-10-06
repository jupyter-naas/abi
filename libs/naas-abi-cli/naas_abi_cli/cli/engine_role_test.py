from naas_abi_cli.cli.engine_role import use_auto_engine_role


def test_cli_engines_serve_only_when_no_engine_does(monkeypatch):
    monkeypatch.delenv("ABI_ENGINE_ROLE", raising=False)

    use_auto_engine_role()

    import os

    assert os.environ["ABI_ENGINE_ROLE"] == "auto"


def test_an_explicit_engine_role_wins(monkeypatch):
    monkeypatch.setenv("ABI_ENGINE_ROLE", "client")

    use_auto_engine_role()

    import os

    assert os.environ["ABI_ENGINE_ROLE"] == "client"
