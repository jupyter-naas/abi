from click.testing import CliRunner
from naas_abi_core.engine.nats_auth import module_key

from naas_abi_cli.cli.module import module

SECRET = "s" * 48


def test_module_key_prints_the_key_of_a_module_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("NATS_JWT_SECRET", raising=False)
    (tmp_path / ".env").write_text(f"NATS_JWT_SECRET={SECRET}\n")

    result = CliRunner().invoke(module, ["key", "demo.research"])

    assert result.exit_code == 0, result.output
    assert result.output.strip() == module_key(SECRET, "demo.research")


def test_module_key_refuses_a_first_party_identity(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NATS_JWT_SECRET", SECRET)

    result = CliRunner().invoke(module, ["key", "api"])

    assert result.exit_code != 0 and "first-party" in result.output


def test_module_key_needs_the_project_secret(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("NATS_JWT_SECRET", raising=False)

    result = CliRunner().invoke(module, ["key", "demo.research"])

    assert result.exit_code != 0 and "NATS_JWT_SECRET" in result.output
