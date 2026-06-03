"""Tests for the process-wide context accessors in ``engine/context.py``.

Focus: the readiness fence on ``get_default_model_registry`` — it must raise
if called before ``Engine.load()`` has finished binding the singleton, so a
module's ``on_load`` cannot accidentally read a half-populated registry via
the global accessor.
"""

from __future__ import annotations

from typing import Iterator

import pytest

from naas_abi_core.engine import context
from naas_abi_core.engine.context import (
    get_default_model_registry,
    set_default_model_registry,
    with_model_registry_override,
)
from naas_abi_core.services.model_registry.ModelRegistryService import (
    ModelRegistryService,
)


@pytest.fixture(autouse=True)
def _reset_singleton() -> Iterator[None]:
    """Each test starts from the pre-load state and leaves no residue."""
    context._default_model_registry = None
    context._default_model_registry_ready = False
    try:
        yield
    finally:
        context._default_model_registry = None
        context._default_model_registry_ready = False


def test_raises_when_called_before_engine_load() -> None:
    """The whole point of the fence: a module's on_load reaching for the
    accessor pre-init must fail loudly with an actionable message rather
    than silently get a half-populated registry (or None)."""
    with pytest.raises(RuntimeError) as exc_info:
        get_default_model_registry()
    msg = str(exc_info.value)
    # Names the function and explains the lifecycle expectation.
    assert "get_default_model_registry" in msg
    assert "Engine.load" in msg
    # Points at the in-load alternative.
    assert "self._engine.services.model_registry" in msg


def test_returns_registry_after_set() -> None:
    registry = ModelRegistryService()
    set_default_model_registry(registry)
    assert get_default_model_registry() is registry


def test_returns_none_after_set_none() -> None:
    """``Engine.load()`` calls ``set_default_model_registry(None)`` when the
    engine has no registry configured — a valid post-init state. Callers
    that legitimately handle absence (e.g. fall back to a direct OpenAI
    client) must still see ``None`` rather than a RuntimeError."""
    set_default_model_registry(None)
    assert get_default_model_registry() is None


def test_override_bypasses_ready_check() -> None:
    """Test fixtures install fakes via ``with_model_registry_override``
    without going through Engine.load — that path must work even when the
    ready flag is False."""
    fake = ModelRegistryService()
    assert context._default_model_registry_ready is False
    with with_model_registry_override(fake):
        assert get_default_model_registry() is fake
    # After exit, ready is still False — accessor goes back to raising.
    with pytest.raises(RuntimeError):
        get_default_model_registry()


def test_override_wins_over_real_registry() -> None:
    real = ModelRegistryService()
    fake = ModelRegistryService()
    set_default_model_registry(real)
    with with_model_registry_override(fake):
        assert get_default_model_registry() is fake
    # After exit, the bound real registry is what's returned.
    assert get_default_model_registry() is real
