"""Existing configurations must boot without the optional NATS installation."""

import subprocess
import sys
import textwrap
from unittest.mock import MagicMock

import pytest


@pytest.mark.parametrize("nats_config", ["", "nats: null\n"])
def test_legacy_config_loads_and_shuts_down_without_nats(tmp_path, nats_config):
    config = tmp_path / "config.yaml"
    config.write_text(
        "api: {}\n"
        "global_config: {ai_mode: cloud, skip_ontology_loading: true}\n"
        "modules: []\n"
        "services:\n"
        "  secret: {secret_adapters: []}\n"
        "  bus: {bus_adapter: {adapter: python_queue, config: {}}}\n"
        "  kv: {kv_adapter: {adapter: python, config: {}}}\n"
        + nats_config
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            textwrap.dedent(
                """
                import importlib.abc
                import sys
                from pathlib import Path

                class NoNats(importlib.abc.MetaPathFinder):
                    def find_spec(self, fullname, path=None, target=None):
                        if fullname == "nats" or fullname.startswith("nats."):
                            raise ModuleNotFoundError("NATS extra is not installed", name=fullname)

                sys.meta_path.insert(0, NoNats())
                from naas_abi_core.engine.Engine import Engine

                engine = Engine(Path(sys.argv[1]).read_text())
                assert engine.configuration.nats is None
                engine.shutdown()  # also safe before load
                engine.load()
                kv = engine.configuration.services.kv.load()
                kv.set("legacy-key", b"still works")
                assert kv.get("legacy-key") == b"still works"
                bus = engine.configuration.services.bus.load()
                bus.publish("legacy", "event", b"still works")
                storage = engine.configuration.services.object_storage.load()
                storage.put_object("legacy", "file", b"still works")
                assert storage.get_object("legacy", "file") == b"still works"
                engine.shutdown()
                engine.shutdown()
                assert "naas_abi_core.engine.nats_runtime" not in sys.modules
                assert "naas_abi_core.engine.nats_rpc" not in sys.modules
                assert "naas_abi_core.engine.engine_loaders.EngineNATSLoader" not in sys.modules
                """
            ),
            str(config),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_explicit_nats_config_still_exposes_services(monkeypatch):
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_core.engine.engine_loaders.EngineNATSLoader import EngineNATSLoader

    expose = MagicMock(return_value=[])
    close = MagicMock()
    monkeypatch.setattr(EngineNATSLoader, "expose_services", expose)
    monkeypatch.setattr("naas_abi_core.engine.nats_runtime.close", close)
    engine = Engine(
        "api: {}\n"
        "global_config: {ai_mode: cloud}\n"
        "modules: []\n"
        "services: {secret: {secret_adapters: []}}\n"
        "nats: {jwt_secret: test-secret}\n"
    )
    engine.shutdown()
    close.assert_not_called()

    engine.load()
    expose.assert_called_once_with(engine.services)
    engine.shutdown()
    close.assert_called_once()
