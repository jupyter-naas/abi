"""Session hooks for every naas-abi-core test."""

# ABI_REQUIRE_NATS_SERVER=1 (CI) fails broker tests instead of skipping them.
from naas_abi_core.engine.nats_test_server import (  # noqa: F401
    pytest_runtest_makereport,
)
