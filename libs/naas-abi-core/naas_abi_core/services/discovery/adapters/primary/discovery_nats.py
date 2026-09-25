from __future__ import annotations

from functools import partial
from typing import Any

from google.protobuf.message import DecodeError
from naas_abi_core import logger
from naas_abi_core.engine.nats_auth import (
    InvalidServiceTokenError,
    verify_service_token,
)
from naas_abi_core.services.discovery.discovery_service import (
    DiscoveryError,
    DiscoveryService,
)
from naas_abi_proto.discovery.v1 import discovery_pb2 as pb
from nats.aio.client import Client
from nats.aio.msg import Msg
from nats.aio.subscription import Subscription

OPERATIONS: dict[str, tuple[Any, Any, bool]] = {
    "authorize_agent": (pb.AuthorizeAgentRequest, pb.AuthorizeAgentResponse, True),
    "register": (pb.RegisterRequest, pb.RegisterResponse, True),
    "renew": (pb.RenewRequest, pb.RenewResponse, True),
    "unregister": (pb.UnregisterRequest, pb.UnregisterResponse, True),
    "get_module": (pb.GetModuleRequest, pb.GetModuleResponse, False),
    "list_modules": (pb.ListModulesRequest, pb.ListModulesResponse, False),
}


class DiscoveryNATS:
    def __init__(self, service: DiscoveryService, secret: str, project: str):
        self.service, self.secret, self.project = service, secret, project
        self.subscriptions: list[Subscription] = []
        self.max_payload = 512 * 1024

    async def start(self, nc: Client) -> None:
        self.max_payload = min(nc.max_payload, 512 * 1024)
        try:
            for operation in OPERATIONS:
                self.subscriptions.append(
                    await nc.subscribe(
                        f"abi.discovery.{self.project}.v1.{operation}",
                        queue=f"abi.discovery.{self.project}.owners",
                        cb=partial(self._handle, operation),
                    )
                )
            await nc.flush()
        except BaseException:
            await self.stop()
            raise

    async def stop(self) -> None:
        for subscription in self.subscriptions:
            await subscription.drain()
        self.subscriptions.clear()

    async def _handle(self, operation: str, msg: Msg) -> None:
        request_type, response_type, mutation = OPERATIONS[operation]
        response = response_type()
        try:
            owner = verify_service_token(
                (msg.headers or {}).get("Nats-Auth-Token", ""), self.secret
            )
            if len(msg.data) > self.max_payload:
                raise DiscoveryError(
                    "PAYLOAD_TOO_LARGE", "Discovery request exceeds limit"
                )
            request = request_type.FromString(msg.data)
            caller = (
                verify_service_token(request.caller_token, self.secret)
                if operation == "authorize_agent"
                else None
            )
            handler = getattr(self.service, operation)
            response = (
                await handler(request, owner) if mutation else await handler(request)
            )
            if caller is not None:
                response.caller_identity = caller
        except InvalidServiceTokenError:
            response.error.code, response.error.message = (
                "UNAUTHENTICATED",
                "Missing or invalid service token",
            )
        except DecodeError:
            response.error.code, response.error.message = (
                "INVALID_ARGUMENT",
                "Malformed protobuf",
            )
        except DiscoveryError as exc:
            response.error.code, response.error.message = exc.code, str(exc)
        except Exception:  # noqa: BLE001 - translate adapter failures at the RPC boundary
            logger.exception("Discovery request failed")
            response.error.code, response.error.message = (
                "UNAVAILABLE",
                "Registry operation failed",
            )
        if len(response.SerializeToString()) > self.max_payload:
            response = response_type()
            response.error.code, response.error.message = (
                "PAYLOAD_TOO_LARGE",
                "Discovery response exceeds limit",
            )
        if msg.reply:
            await msg.respond(response.SerializeToString())
