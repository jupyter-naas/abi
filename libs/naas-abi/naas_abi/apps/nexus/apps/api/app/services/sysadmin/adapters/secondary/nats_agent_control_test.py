import asyncio

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.nats_agent_control import (
    NatsAgentControl,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures
from naas_abi_proto.agent.v1 import agent_pb2 as pb
from naas_abi_sdk.agent import agent_subject
from naas_abi_sdk.transport import RPCError
from nats.errors import NoRespondersError

RUNNING = fixtures.agent_runs()[3]


class Transport:
    def __init__(self, error=None):
        self.calls, self.error = [], error

    async def call(self, subject, request, response_type, **_options):
        self.calls.append((subject, request))
        if self.error:
            raise self.error
        return response_type()


def test_cancels_on_the_owner_instance_subject():
    transport = Transport()

    asyncio.run(NatsAgentControl(lambda: transport, "zen").cancel(RUNNING))

    ((subject, request),) = transport.calls
    assert subject == agent_subject("zen", "i-2", "Researcher", "cancel")
    assert request == pb.CancelRequest(invocation_id="inv-4", output_format=2)


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (NoRespondersError(), "owner instance i-2 is not running"),
        (RPCError("OWNER_UNAVAILABLE", "not owned here"), "OWNER_UNAVAILABLE"),
        (RPCError("PERMISSION_DENIED", "another caller"), "PERMISSION_DENIED"),
    ],
)
def test_failures_make_the_source_unavailable(error, reason):
    with pytest.raises(SourceUnavailable, match=reason) as raised:
        asyncio.run(NatsAgentControl(lambda: Transport(error), "zen").cancel(RUNNING))
    assert raised.value.source == "agents"
