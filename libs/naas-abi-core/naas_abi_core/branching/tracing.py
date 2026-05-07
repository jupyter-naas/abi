"""OpenTelemetry helper: tag spans with the active branch.

The shape is a single function, ``add_branch_to_span(span, *, key="abi.branch")``,
that calls ``span.set_attribute(key, BranchContext.current())`` if a span
is provided. Anything duck-typed as "has ``set_attribute(name, value)``"
works — the function does not import the OpenTelemetry SDK, so the
branching package stays free of an OTel dependency.

Convention
----------

The attribute key is ``abi.branch`` (Anthropic-style "abi" prefix to
namespace it from generic OpenTelemetry semconv attributes). Spans
emitted by ``naas_abi_core`` services should call this helper at span
creation; consumers building their own spans are encouraged to do the
same so traces from multiple branches stay distinguishable in any
trace backend.

Usage
-----

::

    from opentelemetry import trace
    from naas_abi_core.branching import add_branch_to_span

    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("triple_store.query") as span:
        add_branch_to_span(span)
        ...
"""

from __future__ import annotations

from typing import Any, Protocol

from .context import BranchContext


DEFAULT_BRANCH_SPAN_ATTRIBUTE = "abi.branch"
"""Span attribute key used by ``add_branch_to_span``. Documented as a
constant so callers can reference it in dashboards and trace queries."""


class _SetAttributeSpan(Protocol):
    """Minimal structural type for any span object with
    ``set_attribute``. Matches the OpenTelemetry SDK's ``Span`` and
    ``trace.NonRecordingSpan`` without an import dependency."""

    def set_attribute(self, key: str, value: Any) -> Any: ...


def add_branch_to_span(
    span: _SetAttributeSpan | None,
    *,
    key: str = DEFAULT_BRANCH_SPAN_ATTRIBUTE,
) -> None:
    """Tag ``span`` with the active branch under ``key``.

    A ``None`` span is a no-op, so callers can safely pass
    ``trace.get_current_span()`` without checking whether tracing is
    actually active. If the span object lacks ``set_attribute`` the
    ``AttributeError`` propagates — that is a programming error in the
    caller, not something to silently swallow.
    """
    if span is None:
        return
    span.set_attribute(key, BranchContext.current())
