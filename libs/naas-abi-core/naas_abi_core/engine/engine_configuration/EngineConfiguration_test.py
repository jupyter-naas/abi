import pytest

from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    EngineConfiguration,
)


def _configuration_yaml(
    title: str, dotenv_path: str, reload: bool | None = None
) -> str:
    reload_line = f"\n  reload: {str(reload).lower()}" if reload is not None else ""
    return f"""
api:
  title: "{title}"
  description: "API for ABI"
  logo_path: "assets/logo.png"
  favicon_path: "assets/favicon.ico"
  cors_origins:
    - "http://localhost:9879"{reload_line}

global_config:
  ai_mode: "cloud"

modules:
  - module: naas_abi
    enabled: true
    config: {{}}

services:
  secret:
    secret_adapters:
      - adapter: "dotenv"
        config:
          path: "{dotenv_path}"
  object_storage:
    object_storage_adapter:
      adapter: "fs"
      config:
        base_path: "storage/datastore"
  triple_store:
    triple_store_adapter:
      adapter: "fs"
      config:
        store_path: "storage/triplestore"
        triples_path: "triples"
  vector_store:
    vector_store_adapter:
      adapter: "qdrant_in_memory"
      config: {{}}
  bus:
    bus_adapter:
      adapter: "python_queue"
      config: {{}}
  kv:
    kv_adapter:
      adapter: "python"
      config: {{}}
""".strip()


def test_load_configuration_uses_dotenv_configured_in_secret_service(
    tmp_path, monkeypatch
):
    (tmp_path / ".env.bootstrap").write_text("ENV=dev\n", encoding="utf-8")
    (tmp_path / "config.yaml").write_text(
        _configuration_yaml(title="BASE", dotenv_path=".env.bootstrap"),
        encoding="utf-8",
    )
    (tmp_path / "config.dev.yaml").write_text(
        _configuration_yaml(title="DEV", dotenv_path=".env.bootstrap"),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ENV", raising=False)

    configuration = EngineConfiguration.load_configuration()

    assert configuration.api.title == "DEV"
    assert configuration.api.reload is True


def test_load_configuration_allows_disabling_api_reload(tmp_path, monkeypatch):
    (tmp_path / ".env.bootstrap").write_text("ENV=local\n", encoding="utf-8")
    (tmp_path / "config.yaml").write_text(
        _configuration_yaml(title="BASE", dotenv_path=".env.bootstrap", reload=False),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ENV", raising=False)

    configuration = EngineConfiguration.load_configuration()

    assert configuration.api.reload is False


def test_load_configuration_fails_if_configured_dotenv_file_is_missing(
    tmp_path, monkeypatch
):
    (tmp_path / "config.yaml").write_text(
        _configuration_yaml(title="BASE", dotenv_path=".env.missing"),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ENV", raising=False)

    with pytest.raises(FileNotFoundError, match=".env.missing"):
        EngineConfiguration.load_configuration()


def test_from_yaml_content_fails_if_configured_dotenv_file_is_missing():
    with pytest.raises(FileNotFoundError, match=".env.missing"):
        EngineConfiguration.from_yaml_content(
            _configuration_yaml(title="BASE", dotenv_path=".env.missing")
        )
