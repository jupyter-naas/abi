"""Tests for local ``abi dev`` resolution helpers."""

from __future__ import annotations

import json

import pytest
from naas_abi_core.services.triple_store.resolve import (
    abi_dev_service_port,
    load_abi_dev_instance,
    resolve_local_http_url,
)


def _write_instance(tmp_path, *, ports: dict[str, int]) -> None:
    instance_dir = tmp_path / ".abi" / "dev"
    instance_dir.mkdir(parents=True)
    (instance_dir / "instance.json").write_text(
        json.dumps({"ports": ports}),
        encoding="utf-8",
    )


def test_load_abi_dev_instance_walks_up_to_project_root(tmp_path):
    _write_instance(tmp_path, ports={"oxigraph": 8639})
    module_dir = tmp_path / "src" / "module"
    module_dir.mkdir(parents=True)

    instance = load_abi_dev_instance(start=module_dir)

    assert instance is not None
    assert instance["ports"]["oxigraph"] == 8639


def test_resolve_local_http_url_prefers_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OXIGRAPH_URL", "http://example.test:9999")

    assert (
        resolve_local_http_url(
            "oxigraph",
            env_var="OXIGRAPH_URL",
            default_url="http://localhost:7878",
        )
        == "http://example.test:9999"
    )


def test_resolve_local_http_url_reads_abi_dev_instance(tmp_path):
    _write_instance(tmp_path, ports={"oxigraph": 8639})
    module_dir = tmp_path / "src" / "module"
    module_dir.mkdir(parents=True)

    assert (
        resolve_local_http_url(
            "oxigraph",
            env_var="OXIGRAPH_URL",
            default_url="http://localhost:7878",
            start=module_dir,
        )
        == "http://127.0.0.1:8639"
    )


def test_abi_dev_service_port_uses_probe_host(
    monkeypatch: pytest.MonkeyPatch, tmp_path
):
    _write_instance(tmp_path, ports={"api": 7001})
    monkeypatch.setenv("ABI_DEV_BIND_HOST", "0.0.0.0")  # nosec B104 - test wildcard bind normalization

    assert abi_dev_service_port("api", start=tmp_path) == 7001
    assert (
        resolve_local_http_url(
            "api",
            env_var="ABI_PORT",
            default_url="http://localhost:9879",
            start=tmp_path,
        )
        == "http://127.0.0.1:7001"
    )


def test_resolve_local_http_url_falls_back_to_default(tmp_path):
    module_dir = tmp_path / "src" / "module"
    module_dir.mkdir(parents=True)

    assert (
        resolve_local_http_url(
            "oxigraph",
            env_var="OXIGRAPH_URL",
            default_url="http://localhost:7878",
            start=module_dir,
        )
        == "http://localhost:7878"
    )
