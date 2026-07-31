"""The Nexus API's Ollama layer must agree with the marketplace module.

These tests exist because it didn't. The API hardcoded ``localhost:11434``
(unreachable from inside a container, and the wrong host under WSL) and
``qwen3-vl:2b`` (a model a new project never pulls), while the module a new
project actually enables resolved the endpoint per platform and shipped
``qwen2.5:3b``. A user who followed the generated README was told by the UI to
install a different model.

Nothing here asserts a *literal* endpoint or tag — that would just re-encode
the drift. They assert the two layers read the same source.
"""

from __future__ import annotations

import inspect

import naas_abi.apps.nexus.apps.api.app.services.ollama as nexus_ollama
import pytest
from naas_abi_marketplace.ai.ollama import defaults as marketplace_defaults


def test_default_model_comes_from_the_marketplace_module() -> None:
    """The tag the API advertises is the tag the project installs."""
    assert nexus_ollama.DEFAULT_MODEL == marketplace_defaults.DEFAULT_CHAT_MODEL_TAG


def test_marketplace_defaults_import_without_the_ai_ollama_extra() -> None:
    """``defaults`` and ``endpoint`` must not pull in ``langchain_ollama``.

    The API imports both, and it does not depend on the ollama module being
    enabled — so a top-level langchain import in the package would break the
    API on any installation without the extra.

    Runs in a subprocess: faking a missing dependency means tearing modules
    out of ``sys.modules``, which leaks into whatever runs next in the same
    interpreter.
    """
    import subprocess
    import sys

    script = """
import builtins
_real = builtins.__import__
def blocked(name, *a, **k):
    if name.startswith("langchain_ollama"):
        raise ImportError("ai-ollama extra not installed")
    return _real(name, *a, **k)
builtins.__import__ = blocked

from naas_abi_marketplace.ai.ollama.defaults import DEFAULT_CHAT_MODEL_TAG
from naas_abi_marketplace.ai.ollama.endpoint import DEFAULT_BASE_URL
assert DEFAULT_CHAT_MODEL_TAG and DEFAULT_BASE_URL
print("ok")
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True
    )
    assert result.returncode == 0, (
        "importing the ollama defaults/endpoint requires langchain_ollama:\n"
        f"{result.stderr}"
    )
    assert "ok" in result.stdout


def test_resolve_endpoint_honours_the_abi_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A container sets ABI_OLLAMA_BASE_URL; the API must follow it."""
    nexus_ollama.resolve_endpoint.cache_clear()
    monkeypatch.setenv("ABI_OLLAMA_BASE_URL", "http://host.docker.internal:11434")
    try:
        assert nexus_ollama.resolve_endpoint() == "http://host.docker.internal:11434"
    finally:
        nexus_ollama.resolve_endpoint.cache_clear()


def test_resolve_endpoint_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    """Resolution probes the network and is called per request."""
    nexus_ollama.resolve_endpoint.cache_clear()
    calls: list[int] = []

    def counting_resolve(*args: object, **kwargs: object) -> tuple[str, bool]:
        calls.append(1)
        return "http://example.invalid:11434", False

    monkeypatch.setattr(nexus_ollama, "resolve_base_url", counting_resolve)
    try:
        first = nexus_ollama.resolve_endpoint()
        second = nexus_ollama.resolve_endpoint()
        assert first == second == "http://example.invalid:11434"
        assert len(calls) == 1, "resolve_endpoint must not re-probe on every call"
    finally:
        nexus_ollama.resolve_endpoint.cache_clear()


def test_resolve_endpoint_survives_a_broken_resolver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Endpoint resolution is best-effort — it must never take the API down."""
    nexus_ollama.resolve_endpoint.cache_clear()

    def exploding(*args: object, **kwargs: object) -> tuple[str, bool]:
        raise OSError("no network")

    monkeypatch.setattr(nexus_ollama, "resolve_base_url", exploding)
    try:
        assert nexus_ollama.resolve_endpoint() == nexus_ollama.DEFAULT_BASE_URL
    finally:
        nexus_ollama.resolve_endpoint.cache_clear()


@pytest.mark.parametrize(
    "func_name",
    ["is_ollama_running", "get_installed_models", "get_ollama_status", "pull_model"],
)
def test_endpoint_arguments_default_to_resolution_not_a_literal(
    func_name: str,
) -> None:
    """``endpoint`` defaults must be ``None`` so resolution happens per call.

    A literal default would be bound at import time, which is both wrong
    (localhost) and un-overridable by the environment.
    """
    func = getattr(nexus_ollama, func_name)
    endpoint_param = inspect.signature(func).parameters["endpoint"]
    assert endpoint_param.default is None


def test_no_hardcoded_ollama_endpoint_in_the_api() -> None:
    """Guards the regression directly: no stray ``localhost:11434`` literals.

    The one permitted occurrence is the defensive ImportError fallback in
    this service, which only fires if the marketplace package is missing.
    """
    import pathlib
    import re

    # A *quoted* ollama URL — i.e. a real string literal in code, not prose
    # describing one in a docstring or comment.
    literal = re.compile(r"""['"]https?://[^'"]*11434""")

    api_root = pathlib.Path(nexus_ollama.__file__).parent.parent
    offenders: list[str] = []

    for path in api_root.rglob("*.py"):
        if path.name.endswith("_test.py"):
            continue
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not literal.search(line) or line.lstrip().startswith("#"):
                continue
            is_the_allowed_fallback = (
                path.name == "ollama.py" and "DEFAULT_BASE_URL =" in line
            )
            if not is_the_allowed_fallback:
                offenders.append(f"{path.relative_to(api_root)}:{lineno}: {line.strip()}")

    assert not offenders, "hardcoded ollama endpoint(s):\n" + "\n".join(offenders)
