"""ABI_REQUIRE_NATS_SERVER=1 turns a skip for want of nats-server into a failure."""

from pathlib import Path

import pytest

pytest_plugins = ["pytester"]

VARIABLE = "ABI_REQUIRE_NATS_SERVER"

BROKER_SUITE = """
import pytest


@pytest.fixture
def broker():
    pytest.skip("nats-server is not installed")


@pytest.mark.skipif(True, reason="nats-server not installed")
def test_marked():
    pass


def test_fixture(broker):
    pass


def test_body():
    pytest.skip("nats-server is not installed")


def test_other_reason():
    pytest.skip("a different reason")


@pytest.mark.xfail(reason="nats-server flake")
def test_expected_failure():
    raise AssertionError


def test_passes():
    pass
"""


@pytest.fixture
def suite(pytester):
    # The hook under test is this directory's conftest.
    pytester.makeconftest(Path(__file__).with_name("conftest.py").read_text())
    pytester.makepyfile(test_broker=BROKER_SUITE)
    return pytester


def test_broker_suites_skip_without_the_variable(suite, monkeypatch):
    monkeypatch.delenv(VARIABLE, raising=False)

    suite.runpytest().assert_outcomes(passed=1, skipped=4, xfailed=1)


def test_the_variable_fails_every_skip_for_want_of_nats_server(suite, monkeypatch):
    monkeypatch.setenv(VARIABLE, "1")

    result = suite.runpytest("-rfE")

    # Skips in setup (mark, fixture) become errors, a skip in the body a failure.
    result.assert_outcomes(passed=1, skipped=1, errors=2, failed=1, xfailed=1)
    result.stdout.fnmatch_lines([f"*{VARIABLE}=1*nats-server*"])
