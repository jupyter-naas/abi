"""Tests for ``BranchContextLogFilter``."""

from __future__ import annotations

import logging
from io import StringIO

import pytest

from .context import BranchContext
from .logging import BranchContextLogFilter


@pytest.fixture
def captured() -> tuple[logging.Logger, StringIO]:
    """A fresh logger + a string buffer capturing its output, scoped to
    the test so test order can't pollute global handler state."""
    logger = logging.getLogger(f"test.branching.{id(object())}")
    logger.handlers.clear()
    logger.setLevel(logging.DEBUG)
    buf = StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(logging.Formatter("%(branch)s | %(message)s"))
    handler.addFilter(BranchContextLogFilter())
    logger.addHandler(handler)
    return logger, buf


def test_default_branch_in_record(captured):
    logger, buf = captured
    logger.info("hello")
    assert buf.getvalue().strip() == "main | hello"


def test_active_branch_in_record(captured):
    logger, buf = captured
    with BranchContext.use("feature-x"):
        logger.info("hi")
    assert buf.getvalue().strip() == "feature-x | hi"


def test_explicit_extra_wins(captured):
    """``logger.log(..., extra={'branch': 'override'})`` wins over the
    ambient capture — explicit always beats implicit."""
    logger, buf = captured
    with BranchContext.use("feature-x"):
        logger.info("hi", extra={"branch": "override"})
    assert buf.getvalue().strip() == "override | hi"


def test_filter_never_drops_records(captured):
    logger, buf = captured
    f = BranchContextLogFilter()
    record = logger.makeRecord(
        logger.name, logging.INFO, __file__, 0, "msg", (), None
    )
    assert f.filter(record) is True
    assert getattr(record, "branch") == BranchContext.current()


def test_custom_attribute_name():
    logger = logging.getLogger("test.branching.custom")
    logger.handlers.clear()
    logger.setLevel(logging.DEBUG)
    buf = StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(logging.Formatter("%(workspace)s | %(message)s"))
    handler.addFilter(BranchContextLogFilter(attribute="workspace"))
    logger.addHandler(handler)
    with BranchContext.use("feature-x"):
        logger.info("hi")
    assert buf.getvalue().strip() == "feature-x | hi"
