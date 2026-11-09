import asyncio

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.nats_agent_control import (
    NatsAgentControl,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures
from naas_abi_proto.agent.v1 import agent_pb2 as pb
from naas_abi_proto.discovery.v1 import discovery_pb2 as discovery_pb
from naas_abi_sdk.agent import agent_subject
from naas_abi_sdk.transport import RPCError
from nats.errors import NoRespondersError

RUNNING = fixtures.agent_runs()[3]


class Transport:
    """Discovery lists the owner instance; the agent call fails with ``error``."""

    def __init__(self, error=None, discovery_error=None):
        self.calls, self.error, self.discovery_error = [], error, discovery_error

    async def call(self, subject, request, response_type, **_options):
        self.calls.append((subject, request))
        if subject.startswith("abi.discovery."):
            if self.discovery_error:
                raise self.discovery_error
            return discovery_pb.ListModulesResponse(
                instances=[
                    discovery_pb.Instance(instance_id="i-1", service_account="a1"),
                    discovery_pb.Instance(instance_id="i-2", service_account="b2"),
                ]
            )
        if self.error:
            raise self.error
        return response_type()


def test_cancels_on_the_owner_instance_subject():
    """The owner's subjects carry its service account, read from discovery."""
    transport = Transport()

    asyncio.run(NatsAgentControl(lambda: transport, "zen").cancel(RUNNING))

    subject, request = transport.calls[-1]
    assert subject == agent_subject("zen", "b2", "i-2", "Researcher", "cancel")
    assert request == pb.CancelRequest(invocation_id="inv-4", output_format=2)


def test_a_discovery_failure_makes_the_source_unavailable():
    transport = Transport(discovery_error=NoRespondersError())
    with pytest.raises(SourceUnavailable, match="discovery") as raised:
        asyncio.run(NatsAgentControl(lambda: transport, "zen").cancel(RUNNING))
    assert raised.value.source == "agents"
    assert not any(s.startswith("abi.agent.") for s, _ in transport.calls)


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
