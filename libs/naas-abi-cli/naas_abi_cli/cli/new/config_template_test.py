"""Render checks for the generated project config templates.

The ``code`` feature flag (in-app coding workspaces) must only be enabled when a
project is generated with the coding stack (``--with-coding`` → ``include_coding``),
and only for workspace admins (owner + admin) — never for members/viewers.
"""

from __future__ import annotations

import os

import jinja2
import naas_abi_cli
import yaml

_TEMPLATE = os.path.join(
    os.path.dirname(naas_abi_cli.__file__),
    "cli/new/templates/project/config.local.yaml",
)

_BASE_VALUES = {
    "project_name": "Demo",
    "project_name_snake": "demo",
    "project_name_pascal": "Demo",
    "base_domain": "localhost",
    "public_web_host": "localhost",
    "public_api_host": "api.localhost",
}


def _render_feature_flags(*, include_coding: bool) -> dict:
    src = open(_TEMPLATE, encoding="utf-8").read()
    rendered = jinja2.Template(src).render({**_BASE_VALUES, "include_coding": include_coding})
    doc = yaml.safe_load(rendered)  # also asserts the render is valid YAML
    return doc["modules"][0]["config"]["nexus_config"]["feature_flags"]


def test_code_enabled_for_admins_when_coding_included() -> None:
    ff = _render_feature_flags(include_coding=True)

    assert "code" in ff["enabled_features"]
    assert "code" in ff["role_baseline"]["owner"]
    assert "code" in ff["role_baseline"]["admin"]
    # Members and viewers never get the coding section by default.
    assert "code" not in ff["role_baseline"]["member"]
    assert "code" not in ff["role_baseline"]["viewer"]


def test_code_absent_when_coding_not_included() -> None:
    ff = _render_feature_flags(include_coding=False)

    assert "code" not in ff["enabled_features"]
    for role in ("owner", "admin", "member", "viewer"):
        assert "code" not in ff["role_baseline"][role]
