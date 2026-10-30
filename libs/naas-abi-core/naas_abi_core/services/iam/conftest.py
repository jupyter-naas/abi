"""IAM test fixtures: a bootstrapped service on the memory store, and a fresh
PostgreSQL schema for the tests that run there."""

import os
from collections.abc import Iterator
from uuid import uuid4

import pytest

from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import IAMStoreMemory
from naas_abi_core.services.iam.IAMService import IAMService
from naas_abi_core.services.iam.tests.iam_harness import (
    ACTIVITY_LOG,
    NEXUS,
    TRIPLE_STORE,
    IAMHarness,
)


@pytest.fixture
def iam() -> IAMService:
    service = IAMService(IAMStoreMemory())
    service.bootstrap()
    service._register_catalog(TRIPLE_STORE)
    service._register_catalog(ACTIVITY_LOG)
    service._register_catalog(NEXUS)
    return service


@pytest.fixture
def h(iam) -> IAMHarness:
    return IAMHarness(iam)


def postgres_dsn() -> str:
    """The database the PostgreSQL tests run on: IAM_TEST_POSTGRES_DSN, or the
    document tests' DOCUMENT_TEST_POSTGRES_DSN; the test is skipped otherwise."""
    dsn = os.environ.get("IAM_TEST_POSTGRES_DSN") or os.environ.get(
        "DOCUMENT_TEST_POSTGRES_DSN"
    )
    if not dsn:
        pytest.skip("Set IAM_TEST_POSTGRES_DSN to run on PostgreSQL")
    return dsn


@pytest.fixture
def schema() -> Iterator[tuple[str, str]]:
    """``(dsn, name)`` of a schema no other test uses, dropped after the test
    whatever its outcome."""
    from sqlalchemy import create_engine, text

    from naas_abi_core.services.iam.adapters.secondary.IAMStorePostgreSQL import (
        sqlalchemy_url,
    )

    dsn = postgres_dsn()
    name = f"iam_test_{uuid4().hex[:12]}"
    try:
        yield dsn, name
    finally:
        engine = create_engine(sqlalchemy_url(dsn))
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{name}" CASCADE'))
        engine.dispose()
