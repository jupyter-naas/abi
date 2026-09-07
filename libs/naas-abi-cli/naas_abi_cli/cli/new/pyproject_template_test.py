"""Render checks for the generated project's ``pyproject.toml``.

A scaffolded project resolves the framework from the ``.abi`` submodule rather
than PyPI, so it tracks the checked-out source instead of the last published
release. That only works when ``.abi/libs`` is actually there: ``git`` may be
missing, the clone may fail, or the user may pass ``--without-abi-submodule``.
Emitting the path sources in those cases points uv at directories that do not
exist and breaks project creation outright, so the block is conditional.
"""

from __future__ import annotations

import os
import tomllib

import jinja2

import naas_abi_cli

_TEMPLATE = os.path.join(
    os.path.dirname(naas_abi_cli.__file__),
    "cli/new/templates/project/pyproject.toml",
)

_BASE_VALUES = {
    "project_name": "demo",
    "project_name_snake": "demo",
    "project_name_pascal": "Demo",
    "base_domain": "localhost",
    "public_web_host": "localhost",
    "public_api_host": "api.localhost",
    "include_coding": False,
}

_FRAMEWORK_PACKAGES = {
    "naas-abi",
    "naas-abi-core",
    "naas-abi-marketplace",
    "naas-abi-cli",
}


def _render(*, use_local_abi_sources: bool) -> tuple[dict, str]:
    src = open(_TEMPLATE, encoding="utf-8").read()
    rendered = jinja2.Template(src).render(
        {**_BASE_VALUES, "use_local_abi_sources": use_local_abi_sources}
    )
    # Parsing also asserts the render is valid TOML.
    return tomllib.loads(rendered), rendered


def test_sources_are_live_when_the_submodule_is_present() -> None:
    doc, _ = _render(use_local_abi_sources=True)

    sources = doc["tool"]["uv"]["sources"]
    assert set(sources) == _FRAMEWORK_PACKAGES
    for package, spec in sources.items():
        assert spec["editable"] is True
        assert spec["path"] == f".abi/libs/{package}"


def test_no_sources_without_the_submodule() -> None:
    """Live path sources here would point uv at directories that don't exist."""
    doc, _ = _render(use_local_abi_sources=False)

    assert "sources" not in doc["tool"]["uv"]


def test_the_pypi_variant_still_documents_how_to_switch() -> None:
    _, rendered = _render(use_local_abi_sources=False)

    assert "git submodule add" in rendered
    assert "# [tool.uv.sources]" in rendered


def test_the_override_survives_both_variants() -> None:
    """The onnxruntime pin is unrelated to sourcing and must not be lost."""
    for use_local in (True, False):
        doc, _ = _render(use_local_abi_sources=use_local)
        assert doc["tool"]["uv"]["override-dependencies"] == ["onnxruntime<1.26"]


def test_project_metadata_is_unaffected_by_the_switch() -> None:
    for use_local in (True, False):
        doc, _ = _render(use_local_abi_sources=use_local)
        assert doc["project"]["name"] == "demo"
        assert doc["build-system"]["build-backend"] == "setuptools.build_meta"
