"""ABI_REQUIRE_NATS_SERVER=1 turns a skip for want of nats-server into a failure."""

import pytest
from naas_abi_core.engine.nats_test_server import REQUIRE_NATS_SERVER

pytest_plugins = ["pytester"]

BROKER_SUITE = """
import pytest

pytestmark = pytest.mark.filterwarnings("ignore")


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
    pytest.skip("Docker/Testcontainers unavailable")


@pytest.mark.xfail(reason="nats-server flake")
def test_expected_failure():
    raise AssertionError


def test_passes():
    pass
"""


@pytest.fixture
def suite(pytester):
    pytester.makeconftest(
        "from naas_abi_core.engine.nats_test_server import"
        " pytest_runtest_makereport  # noqa: F401\n"
    )
    pytester.makepyfile(test_broker=BROKER_SUITE)
    return pytester


def test_broker_suites_skip_without_the_variable(suite, monkeypatch):
    monkeypatch.delenv(REQUIRE_NATS_SERVER, raising=False)

    suite.runpytest().assert_outcomes(passed=1, skipped=4, xfailed=1)


def test_the_variable_fails_every_skip_for_want_of_nats_server(suite, monkeypatch):
    monkeypatch.setenv(REQUIRE_NATS_SERVER, "1")

    result = suite.runpytest("-rfE")

    # Skips in setup (mark, fixture) become errors, a skip in the body a failure.
    result.assert_outcomes(passed=1, skipped=1, errors=2, failed=1, xfailed=1)
    result.stdout.fnmatch_lines([f"*{REQUIRE_NATS_SERVER}=1*nats-server*"])


def test_other_values_leave_skips_alone(suite, monkeypatch):
    monkeypatch.setenv(REQUIRE_NATS_SERVER, "0")

    suite.runpytest().assert_outcomes(passed=1, skipped=4, xfailed=1)
