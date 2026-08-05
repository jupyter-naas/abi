from __future__ import annotations

from pathlib import Path

import yaml
from naas_abi.config.module_enable import enable_module_in_config


def test_enable_github_module_writes_module_key_and_config(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.dump({"modules": [{"module": "naas_abi", "enabled": True}]}),
        encoding="utf-8",
    )

    result = enable_module_in_config(
        "naas_abi_marketplace.applications.github",
        config_file=str(config_path),
    )

    assert result.created is True
    assert result.secrets_required == ["GITHUB_ACCESS_TOKEN"]

    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    github = next(
        m
        for m in data["modules"]
        if m.get("module") == "naas_abi_marketplace.applications.github"
    )
    assert github["enabled"] is True
    assert github["config"]["github_access_token"] == "{{ secret.GITHUB_ACCESS_TOKEN }}"


def test_enable_module_is_idempotent(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.dump(
            {
                "modules": [
                    {
                        "module": "naas_abi_marketplace.applications.github",
                        "enabled": False,
                        "config": {"github_access_token": "{{ secret.GITHUB_ACCESS_TOKEN }}"},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = enable_module_in_config(
        "naas_abi_marketplace.applications.github",
        config_file=str(config_path),
    )

    assert result.created is False
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert data["modules"][0]["enabled"] is True
