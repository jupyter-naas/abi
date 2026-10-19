from __future__ import annotations

from functools import partial
from typing import Any

from google.protobuf.message import DecodeError
from naas_abi_core import logger
from naas_abi_core.engine.call_context import use_call_context
from naas_abi_core.engine.nats_auth import (
    HOST_AUDIENCE_PREFIX,
    InvalidServiceTokenError,
    TokenVerifier,
    host_audience,
)
from naas_abi_core.engine.nats_dispatch import max_concurrent_requests
from naas_abi_core.engine.nats_identity import caller_context, for_request, refusal
from naas_abi_core.engine.nats_sessions import stop_delivery
from naas_abi_core.services.discovery.caller import caller_of
from naas_abi_core.services.discovery.discovery_service import (
    DiscoveryError,
    DiscoveryService,
)
from naas_abi_core.services.iam.IAMPorts import PermissionDeniedError
from naas_abi_core.services.iam.modules import subject_token
from naas_abi_proto.discovery.v1 import discovery_pb2 as pb
from naas_abi_sdk import overflow
from naas_abi_sdk.concurrency import ConcurrentCalls
from naas_abi_sdk.messages import reply
from nats.aio.client import Client
from nats.aio.msg import Msg
from nats.aio.subscription import Subscription

OPERATIONS: dict[str, tuple[Any, Any, bool]] = {
    "authorize_agent": (pb.AuthorizeAgentRequest, pb.AuthorizeAgentResponse, True),
    "authorize_model": (pb.AuthorizeModelRequest, pb.AuthorizeModelResponse, True),
    "authorize_app": (pb.AuthorizeAppRequest, pb.AuthorizeAppResponse, True),
    "authorize_job": (pb.AuthorizeJobRequest, pb.AuthorizeJobResponse, True),
    "register": (pb.RegisterRequest, pb.RegisterResponse, True),
    "renew": (pb.RenewRequest, pb.RenewResponse, True),
    "unregister": (pb.UnregisterRequest, pb.UnregisterResponse, True),
    # discovery:Evict on the instance's module.
    "evict": (pb.EvictRequest, pb.EvictResponse, True),
    "get_module": (pb.GetModuleRequest, pb.GetModuleResponse, False),
    "list_modules": (pb.ListModulesRequest, pb.ListModulesResponse, False),
}


class DiscoveryNATS:
    def __init__(
        self,
        service: DiscoveryService,
        verifier: TokenVerifier,
        project: str,
        max_concurrency: int | None = None,
    ):
        self.service, self.verifier, self.project = service, verifier, project
        # What a hosting module forwards as its caller's token: addressed to
        # that host (``abi:host:<host>``), never the caller's own ``abi:nats``
        # token, which a host must not hold, nor one made for another host.
        # Anything else is refused here.
        self.caller_verifier = verifier.for_audiences(
            (), prefixes=(HOST_AUDIENCE_PREFIX,)
        )
        self.subscriptions: list[Subscription] = []
        self.max_payload = 512 * 1024
        # Calls side by side, as the kernel services (nats.max_concurrent_requests).
        self.calls = ConcurrentCalls(
            max_concurrent_requests() if max_concurrency is None else max_concurrency
        )

    async def start(self, nc: Client) -> None:
        self.max_payload = min(nc.max_payload, 512 * 1024)
        try:
            for operation in OPERATIONS:
                self.subscriptions.append(
                    await nc.subscribe(
                        f"abi.discovery.{self.project}.v1.{operation}",
                        queue=f"abi.discovery.{self.project}.owners",
                        cb=self.calls.callback(
                            partial(self._handle, operation), requests=True
                        ),
                    )
                )
            await nc.flush()
        except BaseException:
            await self.stop()
            raise

    async def stop(self) -> None:
        # The broker confirms the UNSUBs first: drain alone can drop a request
        # routed between its PING and its UNSUB (nats_sessions.stop_delivery).
        await stop_delivery(self.subscriptions)
        for subscription in self.subscriptions:
            await subscription.drain()
        self.subscriptions.clear()
        await self.calls.idle()  # the calls received are answered

    async def _handle(self, operation: str, msg: Msg) -> None:
        request_type, response_type, mutation = OPERATIONS[operation]
        response = response_type()
        try:
            context = caller_context(msg.headers, self.verifier)
            owner = context.principal.id
            # An overflow upload is above the broker limit, so above this cap too.
            if len(msg.data) > self.max_payload or overflow.REQUEST_HEADER in (
                msg.headers or {}
            ):
                raise DiscoveryError(
                    "PAYLOAD_TOO_LARGE", "Discovery request exceeds limit"
                )
            request = request_type.FromString(msg.data)
            # The caller a hosting module vouches for: its token and the user
            # it acts for, verified here as a kernel endpoint verifies its own.
            forwarded = (
                caller_of(
                    request.caller_token,
                    request.caller_on_behalf_of,
                    self.caller_verifier,
                    at=getattr(request, "stored_at", 0.0),
                )
                if operation.startswith("authorize_")
                else None
            )
            if forwarded is not None and forwarded.audience != host_audience(
                subject_token(owner)
            ):
                # Made for another host (or for none): a host that read it from
                # a request replays it nowhere, not even at another host.
                raise InvalidServiceTokenError("the caller's token is for another host")
            with use_call_context(for_request(context, request)):
                handler = getattr(self.service, operation)
                if forwarded is not None:
                    response = await handler(request, owner, forwarded)
                elif mutation:
                    response = await handler(request, owner)
                else:
                    response = await handler(request)
        except InvalidServiceTokenError as exc:
            response.error.code, response.error.message = (
                "UNAUTHENTICATED",
                refusal(exc, "Missing or invalid service token"),
            )
        except DecodeError:
            response.error.code, response.error.message = (
                "INVALID_ARGUMENT",
                "Malformed protobuf",
            )
        except DiscoveryError as exc:
            response.error.code, response.error.message = exc.code, str(exc)
        except PermissionDeniedError as exc:
            response.error.code, response.error.message = (
                "PERMISSION_DENIED",
                str(exc),
            )
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
            await reply(msg, response.SerializeToString())
