"""Tests for ``add_branch_to_span`` (no real OTel dependency)."""

from __future__ import annotations

from .context import BranchContext
from .tracing import DEFAULT_BRANCH_SPAN_ATTRIBUTE, add_branch_to_span


class _FakeSpan:
    """Stand-in for the OTel Span protocol — only ``set_attribute``
    is exercised."""

    def __init__(self) -> None:
        self.attrs: dict[str, object] = {}

    def set_attribute(self, key: str, value: object) -> None:
        self.attrs[key] = value


def test_tags_default_branch():
    span = _FakeSpan()
    add_branch_to_span(span)
    assert span.attrs == {DEFAULT_BRANCH_SPAN_ATTRIBUTE: "main"}


def test_tags_active_branch():
    span = _FakeSpan()
    with BranchContext.use("feature-x"):
        add_branch_to_span(span)
    assert span.attrs == {DEFAULT_BRANCH_SPAN_ATTRIBUTE: "feature-x"}


def test_custom_key():
    span = _FakeSpan()
    add_branch_to_span(span, key="my.branch")
    assert span.attrs == {"my.branch": "main"}


def test_none_span_is_noop():
    # No exception — spans default off cleanly when tracing is disabled.
    add_branch_to_span(None)


def test_default_attribute_constant():
    assert DEFAULT_BRANCH_SPAN_ATTRIBUTE == "abi.branch"
