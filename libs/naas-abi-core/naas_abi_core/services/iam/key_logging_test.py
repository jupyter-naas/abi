"""A service key never reaches a log: not in a traceback's variables, not in a
repr, not in what the callout or the token exchange log when the store fails."""

from __future__ import annotations

import asyncio
import os
from types import SimpleNamespace

import pytest
from loguru import logger
from naas_abi_proto.iam.v1 import iam_pb2 as pb

from naas_abi_core.engine.nats_auth_callout import AuthCallout
from naas_abi_core.engine.nats_nkeys import PREFIX_USER, KeyPair
from naas_abi_core.engine.nats_test_tokens import TEST_TOKENS
from naas_abi_core.services.iam import keys
from naas_abi_core.services.iam.adapters.primary.iam__primary_adapter__NATS import (
    IAMPrimaryAdapterNATS,
)
from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import (
    IAMStoreMemory,
)
from naas_abi_core.services.iam.IAMPorts import CreatedKey
from naas_abi_core.services.iam.IAMService import IAMService
from naas_abi_core.utils import Logger

NEW = keys.generate_key("service")
SECRET = NEW.value.rsplit("_", 1)[1]


class _BrokenStore(IAMStoreMemory):
    """A store that fails the way a restarting database does."""

    def get_key(self, key_id):
        raise RuntimeError("database is locked")


class _Sink:
    """Everything loguru writes, formatted with its exception, as a console sink
    would (``diagnose`` as ``Logger`` sets it)."""

    def __init__(self) -> None:
        self.text = ""

    def __call__(self, message) -> None:
        self.text += str(message)


@pytest.fixture
def log():
    sink = _Sink()
    handler = logger.add(sink, level="DEBUG", diagnose=False, backtrace=False)
    yield sink
    logger.remove(handler)


def test_a_key_is_not_in_the_repr_of_what_holds_it():
    assert SECRET not in repr(NEW) and NEW.value not in repr(NEW)
    presented = keys.parse(NEW.value)
    assert SECRET not in repr(presented)
    created = CreatedKey(
        record=SimpleNamespace(key_id="k"),  # type: ignore[arg-type]
        value=NEW.value,
    )
    assert NEW.value not in repr(created)


def test_the_console_log_prints_no_variable_values(capsys):
    """loguru's default prints each frame's variables under a traceback."""
    Logger.reconfigure("DEBUG")
    try:
        presented = NEW.value  # what a traceback would print

        def fail(options):
            raise RuntimeError("boom")

        try:
            fail({"pass": presented})
        except RuntimeError:
            logger.exception("it failed")
    finally:
        Logger.reconfigure(os.environ.get("LOG_LEVEL", "WARNING"))
    err = capsys.readouterr().err
    assert "it failed" in err and "RuntimeError" in err
    assert NEW.value not in err and SECRET not in err


def _callout(iam) -> AuthCallout:
    return AuthCallout(iam, KeyPair.create().seed, "nats://127.0.0.1:1")


def test_a_failing_store_during_a_callout_logs_no_key(log):
    iam = IAMService(_BrokenStore())
    request = {
        "nats": {
            "user_nkey": KeyPair.create(PREFIX_USER).public_key,
            "server_id": {"id": "SERVER"},
            "connect_opts": {"user": "sa", "pass": NEW.value},
        }
    }
    _callout(iam).answer(request)
    assert "could not decide" in log.text and "RuntimeError" in log.text
    assert "Traceback" not in log.text
    assert NEW.value not in log.text and SECRET not in log.text


class _FakeRequest:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.headers: dict[str, str] = {}
        self.subject = "abi.iam.v1.token"
        self.responses: list[bytes] = []

    async def respond(self, data: bytes = b"", headers=None) -> None:
        self.responses.append(data)


def test_a_failing_store_during_a_key_exchange_logs_no_key(log):
    iam = IAMService(_BrokenStore())
    primary = IAMPrimaryAdapterNATS(iam, TEST_TOKENS.verifier)
    request = _FakeRequest(pb.TokenRequest(key=NEW.value).SerializeToString())
    asyncio.run(primary._handle(request, operation="token"))
    response = pb.TokenResponse.FromString(request.responses[0])
    assert response.error.code == "INTERNAL"
    assert "iam NATS token failed" in log.text and "RuntimeError" in log.text
    assert "Traceback" not in log.text
    assert NEW.value not in log.text and SECRET not in log.text
