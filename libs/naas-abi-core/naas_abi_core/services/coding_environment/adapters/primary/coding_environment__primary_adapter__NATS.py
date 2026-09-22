"""NATS RPC primary adapter for the coding_environment kernel domain.

Exposes a real ``ICodingEnvironmentAdapter`` as a NATS micro-service (see
``naas_abi_core/proto/coding_environment/v1/coding_environment.proto`` for
the wire contract and ``naas_abi_core/proto/README.md`` for why it lives
there). This is the server side; the matching client is
``CodingEnvironmentSecondaryAdapterNATSClient``.

Stage 1 auth model (see ``naas_abi_core.engine.nats_auth``): one shared
secret, one claim -- which known first-party process holds the token. Every
incoming request must carry a valid token in the ``Nats-Auth-Token`` header
(``AUTH_HEADER``, imported from ``coding_environment_nats_contract`` below --
that's a neutral module neither adapter owns, so this file and the client's
don't depend on each other; see that module's docstring for why).

``wait_until_ready``/``get_workspace_ui_url``/``get_runtime_binding``/
``get_harness_binding`` are explicitly out of scope for this v1 contract
(see the ``.proto`` file's header comment): they have no endpoint here at
all, so a call to any of them simply cannot reach this adapter.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TypeVar

import nats
import nats.micro
from google.protobuf.message import DecodeError, Message
from naas_abi_core import logger
from naas_abi_core.engine.nats_auth import (
    InvalidServiceTokenError,
    verify_service_token,
)
from naas_abi_core.engine.nats_rpc import respond_protobuf
from naas_abi_core.proto.coding_environment.v1 import coding_environment_pb2
from naas_abi_core.proto.common.v1 import common_pb2
from naas_abi_core.services.coding_environment.adapters.coding_environment_nats_contract import (
    AUTH_HEADER,
    SERVICE_NAME,
    SERVICE_VERSION,
    SUBJECT_PREFIX,
)
from naas_abi_core.services.coding_environment.CodingEnvironmentPorts import (
    AccessDeniedError,
    AgentNeverConnectedError,
    ICodingEnvironmentAdapter,
    ProvisionFailedError,
    ProvisionTimeoutError,
    QuotaExceededError,
    TemplateNotFoundError,
    WorkspaceAccess,
    WorkspaceNameConflictError,
    WorkspaceNotFoundError,
    WorkspaceStatus,
    WorkspaceTemplate,
)
from naas_abi_core.services.coding_environment.CodingEnvironmentService import (
    CodingEnvironmentService,
)
from nats.micro.request import Request
from nats.micro.service import Service

__all__ = [
    "AUTH_HEADER",
    "SERVICE_NAME",
    "SERVICE_VERSION",
    "SUBJECT_PREFIX",
    "CodingEnvironmentPrimaryAdapterNATS",
]

_RequestT = TypeVar("_RequestT", bound=Message)
_ResponseT = TypeVar("_ResponseT", bound=Message)


def _template_to_pb(
    template: WorkspaceTemplate,
) -> coding_environment_pb2.WorkspaceTemplate:
    return coding_environment_pb2.WorkspaceTemplate(
        id=template.id,
        name=template.name,
        active_version_id=template.active_version_id,
    )


def _status_to_pb(status: WorkspaceStatus) -> coding_environment_pb2.WorkspaceStatus:
    return coding_environment_pb2.WorkspaceStatus(
        id=status.id,
        name=status.name,
        phase=status.phase,
        agent_ready=status.agent_ready,
    )


def _access_to_pb(access: WorkspaceAccess) -> coding_environment_pb2.WorkspaceAccess:
    """Convert the port's ``WorkspaceAccess`` into its wire shape.

    ``token``/``expires_at`` are left unset rather than sent as empty
    strings when the adapter didn't populate them, so ``HasField`` on the
    client side reflects "the adapter didn't know this" rather than "this
    really is empty".
    """
    pb = coding_environment_pb2.WorkspaceAccess(url=access.url)
    if access.token is not None:
        pb.token = access.token
    if access.expires_at is not None:
        pb.expires_at = access.expires_at
    return pb


def _params_from_pb(params: dict[str, str]) -> dict[str, str] | None:
    """Collapse an empty/absent proto3 map to ``None``.

    proto3 map fields have no field-presence tracking (unlike ``optional``
    scalars), so a caller that passed ``params=None`` and a caller that
    passed ``params={}`` are indistinguishable on the wire -- both decode to
    an empty map here. ``ICodingEnvironmentAdapter`` methods default
    ``params`` to ``None`` and treat "no params" and "empty params"
    identically, so collapsing the empty map to ``None`` before calling the
    wrapped adapter matches local (in-process) behaviour exactly rather than
    forcing every adapter to also handle an empty-but-present dict.
    """
    return dict(params) if params else None


class CodingEnvironmentPrimaryAdapterNATS:
    """Serves coding_environment over NATS RPC (request/reply).

    Wraps a real adapter *or* the domain service and registers one NATS
    micro-service endpoint per ``ICodingEnvironmentAdapter`` method. Each
    endpoint authenticates the caller via ``Nats-Auth-Token`` before doing
    anything else, then decodes the Protobuf request, calls straight through
    to the wrapped object, and encodes a Protobuf response. Errors -- auth
    failures, known domain exceptions, anything unexpected -- are always
    reported as a normal response carrying a populated ``CallError``, never
    as a crashed handler or a raw NATS-level error.

    Accepts either an ``ICodingEnvironmentAdapter`` (a bare secondary
    adapter, e.g. in tests) or a ``CodingEnvironmentService`` (the real
    engine-loaded domain service) -- deliberately, not for convenience:
    wrapping the raw adapter instead of the domain service would silently
    skip ``CodingEnvironmentService``'s event publishing
    (``WorkspaceProvisioned``/``WorkspaceStarted``/... ) and its
    name-conflict adoption logic for every remote caller, which would only
    diverge from in-process behaviour, not match it. ``EngineNATSLoader``
    always passes the domain service.
    """

    def __init__(
        self,
        adapter: ICodingEnvironmentAdapter | CodingEnvironmentService,
        jwt_secret: str,
    ) -> None:
        self._adapter = adapter
        self._jwt_secret = jwt_secret
        self._service: Service | None = None

    async def start(self, nc: nats.NATS) -> None:
        """Register the ``coding_environment`` NATS service on ``nc``.

        ``nc`` must already be connected -- this adapter never manages the
        connection lifecycle itself, only the service/endpoints layered on
        top of it. Calling this more than once is a no-op.
        """
        if self._service is not None:
            return

        service = await nats.micro.add_service(
            nc,
            name=SERVICE_NAME,
            version=SERVICE_VERSION,
            description="ABI kernel coding_environment domain, exposed over NATS RPC (v1).",
        )
        await service.add_endpoint(
            name="ensure_user",
            subject=f"{SUBJECT_PREFIX}.ensure_user",
            handler=self._handle_ensure_user,
        )
        await service.add_endpoint(
            name="list_templates",
            subject=f"{SUBJECT_PREFIX}.list_templates",
            handler=self._handle_list_templates,
        )
        await service.add_endpoint(
            name="provision",
            subject=f"{SUBJECT_PREFIX}.provision",
            handler=self._handle_provision,
        )
        await service.add_endpoint(
            name="start",
            subject=f"{SUBJECT_PREFIX}.start",
            handler=self._handle_start,
        )
        await service.add_endpoint(
            name="stop",
            subject=f"{SUBJECT_PREFIX}.stop",
            handler=self._handle_stop,
        )
        await service.add_endpoint(
            name="delete",
            subject=f"{SUBJECT_PREFIX}.delete",
            handler=self._handle_delete,
        )
        await service.add_endpoint(
            name="list_environments",
            subject=f"{SUBJECT_PREFIX}.list_environments",
            handler=self._handle_list_environments,
        )
        await service.add_endpoint(
            name="get_status",
            subject=f"{SUBJECT_PREFIX}.get_status",
            handler=self._handle_get_status,
        )
        await service.add_endpoint(
            name="get_logs",
            subject=f"{SUBJECT_PREFIX}.get_logs",
            handler=self._handle_get_logs,
        )
        await service.add_endpoint(
            name="get_access",
            subject=f"{SUBJECT_PREFIX}.get_access",
            handler=self._handle_get_access,
        )
        self._service = service

    async def stop(self) -> None:
        """Deregister the service, draining its subscriptions."""
        service = self._service
        self._service = None
        if service is not None:
            await service.stop()

    # ------------------------------------------------------------------
    # Shared request handling: auth, decode, dispatch, encode.
    # ------------------------------------------------------------------

    async def _handle(
        self,
        request: Request,
        request_cls: type[_RequestT],
        response_cls: Callable[..., _ResponseT],
        call: Callable[[_RequestT], _ResponseT],
    ) -> None:
        if not self._is_authenticated(request):
            await self._respond_error(
                request,
                response_cls,
                "UNAUTHENTICATED",
                "missing or invalid auth token",
                retryable=False,
            )
            return

        parsed_request = request_cls()
        try:
            parsed_request.ParseFromString(request.data)
        except DecodeError:
            await self._respond_error(
                request,
                response_cls,
                "INVALID_ARGUMENT",
                "invalid protobuf request",
                retryable=False,
            )
            return

        try:
            # The adapter port is synchronous and may block for seconds (network
            # round trips, slow backends). Every primary shares ONE event loop and
            # ONE connection (nats_runtime), so run the call on a worker thread:
            # inline it would stall every other endpoint of every service in the
            # process, plus nats-py's own PING/PONG handling.
            response = await asyncio.to_thread(call, parsed_request)
        except ProvisionFailedError as exc:
            await self._respond_error(
                request,
                response_cls,
                "PROVISION_FAILED",
                str(exc),
                retryable=False,
                status=exc.status,
            )
            return
        except ProvisionTimeoutError as exc:
            await self._respond_error(
                request,
                response_cls,
                "PROVISION_TIMEOUT",
                str(exc),
                retryable=True,
                status=exc.status,
            )
            return
        except AgentNeverConnectedError as exc:
            await self._respond_error(
                request,
                response_cls,
                "AGENT_NEVER_CONNECTED",
                str(exc),
                retryable=True,
                status=exc.status,
            )
            return
        except TemplateNotFoundError as exc:
            await self._respond_error(
                request,
                response_cls,
                "TEMPLATE_NOT_FOUND",
                str(exc),
                retryable=False,
                status=exc.status,
            )
            return
        except WorkspaceNotFoundError as exc:
            await self._respond_error(
                request,
                response_cls,
                "WORKSPACE_NOT_FOUND",
                str(exc),
                retryable=False,
                status=exc.status,
            )
            return
        except WorkspaceNameConflictError as exc:
            await self._respond_error(
                request,
                response_cls,
                "WORKSPACE_NAME_CONFLICT",
                str(exc),
                retryable=False,
                status=exc.status,
            )
            return
        except QuotaExceededError as exc:
            await self._respond_error(
                request,
                response_cls,
                "QUOTA_EXCEEDED",
                str(exc),
                retryable=False,
                status=exc.status,
            )
            return
        except AccessDeniedError as exc:
            await self._respond_error(
                request,
                response_cls,
                "ACCESS_DENIED",
                str(exc),
                retryable=False,
                status=exc.status,
            )
            return
        except Exception:  # noqa: BLE001 - a handler must never crash the service
            logger.opt(exception=True).error(
                f"CodingEnvironmentPrimaryAdapterNATS: unexpected error handling {request.subject!r}"
            )
            await self._respond_error(
                request, response_cls, "INTERNAL", "internal error", retryable=True
            )
            return

        await respond_protobuf(request, response, response_cls)

    def _is_authenticated(self, request: Request) -> bool:
        headers = request.headers or {}
        token = headers.get(AUTH_HEADER)
        if not token:
            return False
        try:
            verify_service_token(token, self._jwt_secret)
        except InvalidServiceTokenError:
            return False
        return True

    @staticmethod
    async def _respond_error(
        request: Request,
        response_cls: Callable[..., Message],
        code: str,
        message: str,
        *,
        retryable: bool,
        status: int | None = None,
    ) -> None:
        error = (
            common_pb2.CallError(
                code=code, message=message, retryable=retryable, status=status
            )
            if status is not None
            else common_pb2.CallError(code=code, message=message, retryable=retryable)
        )
        response = response_cls(error=error)
        await respond_protobuf(request, response, response_cls)

    # ------------------------------------------------------------------
    # Endpoint handlers -- one per ICodingEnvironmentAdapter method.
    # ------------------------------------------------------------------

    async def _handle_ensure_user(self, request: Request) -> None:
        await self._handle(
            request,
            coding_environment_pb2.EnsureUserRequest,
            coding_environment_pb2.EnsureUserResponse,
            self._call_ensure_user,
        )

    def _call_ensure_user(
        self, req: coding_environment_pb2.EnsureUserRequest
    ) -> coding_environment_pb2.EnsureUserResponse:
        user_id = self._adapter.ensure_user(
            external_id=req.external_id, email=req.email, username=req.username
        )
        return coding_environment_pb2.EnsureUserResponse(user_id=user_id)

    async def _handle_list_templates(self, request: Request) -> None:
        await self._handle(
            request,
            coding_environment_pb2.ListTemplatesRequest,
            coding_environment_pb2.ListTemplatesResponse,
            self._call_list_templates,
        )

    def _call_list_templates(
        self, req: coding_environment_pb2.ListTemplatesRequest
    ) -> coding_environment_pb2.ListTemplatesResponse:
        templates = self._adapter.list_templates()
        return coding_environment_pb2.ListTemplatesResponse(
            templates=coding_environment_pb2.WorkspaceTemplates(
                templates=[_template_to_pb(t) for t in templates]
            )
        )

    async def _handle_provision(self, request: Request) -> None:
        await self._handle(
            request,
            coding_environment_pb2.ProvisionRequest,
            coding_environment_pb2.ProvisionResponse,
            self._call_provision,
        )

    def _call_provision(
        self, req: coding_environment_pb2.ProvisionRequest
    ) -> coding_environment_pb2.ProvisionResponse:
        status = self._adapter.provision(
            user_id=req.user_id,
            template_id=req.template_id,
            name=req.name,
            params=_params_from_pb(dict(req.params)),
        )
        return coding_environment_pb2.ProvisionResponse(status=_status_to_pb(status))

    async def _handle_start(self, request: Request) -> None:
        await self._handle(
            request,
            coding_environment_pb2.StartRequest,
            coding_environment_pb2.StartResponse,
            self._call_start,
        )

    def _call_start(
        self, req: coding_environment_pb2.StartRequest
    ) -> coding_environment_pb2.StartResponse:
        status = self._adapter.start(
            workspace_id=req.workspace_id, params=_params_from_pb(dict(req.params))
        )
        return coding_environment_pb2.StartResponse(status=_status_to_pb(status))

    async def _handle_stop(self, request: Request) -> None:
        await self._handle(
            request,
            coding_environment_pb2.StopRequest,
            coding_environment_pb2.StopResponse,
            self._call_stop,
        )

    def _call_stop(
        self, req: coding_environment_pb2.StopRequest
    ) -> coding_environment_pb2.StopResponse:
        status = self._adapter.stop(workspace_id=req.workspace_id)
        return coding_environment_pb2.StopResponse(status=_status_to_pb(status))

    async def _handle_delete(self, request: Request) -> None:
        await self._handle(
            request,
            coding_environment_pb2.DeleteRequest,
            coding_environment_pb2.DeleteResponse,
            self._call_delete,
        )

    def _call_delete(
        self, req: coding_environment_pb2.DeleteRequest
    ) -> coding_environment_pb2.DeleteResponse:
        self._adapter.delete(workspace_id=req.workspace_id)
        return coding_environment_pb2.DeleteResponse()

    async def _handle_list_environments(self, request: Request) -> None:
        await self._handle(
            request,
            coding_environment_pb2.ListEnvironmentsRequest,
            coding_environment_pb2.ListEnvironmentsResponse,
            self._call_list_environments,
        )

    def _call_list_environments(
        self, req: coding_environment_pb2.ListEnvironmentsRequest
    ) -> coding_environment_pb2.ListEnvironmentsResponse:
        environments = self._adapter.list_environments(user_id=req.user_id)
        return coding_environment_pb2.ListEnvironmentsResponse(
            environments=coding_environment_pb2.WorkspaceStatuses(
                environments=[_status_to_pb(e) for e in environments]
            )
        )

    async def _handle_get_status(self, request: Request) -> None:
        await self._handle(
            request,
            coding_environment_pb2.GetStatusRequest,
            coding_environment_pb2.GetStatusResponse,
            self._call_get_status,
        )

    def _call_get_status(
        self, req: coding_environment_pb2.GetStatusRequest
    ) -> coding_environment_pb2.GetStatusResponse:
        status = self._adapter.get_status(workspace_id=req.workspace_id)
        return coding_environment_pb2.GetStatusResponse(status=_status_to_pb(status))

    async def _handle_get_logs(self, request: Request) -> None:
        await self._handle(
            request,
            coding_environment_pb2.GetLogsRequest,
            coding_environment_pb2.GetLogsResponse,
            self._call_get_logs,
        )

    def _call_get_logs(
        self, req: coding_environment_pb2.GetLogsRequest
    ) -> coding_environment_pb2.GetLogsResponse:
        lines = self._adapter.get_logs(workspace_id=req.workspace_id)
        return coding_environment_pb2.GetLogsResponse(
            lines=coding_environment_pb2.LogLines(lines=lines)
        )

    async def _handle_get_access(self, request: Request) -> None:
        await self._handle(
            request,
            coding_environment_pb2.GetAccessRequest,
            coding_environment_pb2.GetAccessResponse,
            self._call_get_access,
        )

    def _call_get_access(
        self, req: coding_environment_pb2.GetAccessRequest
    ) -> coding_environment_pb2.GetAccessResponse:
        access = self._adapter.get_access(
            workspace_id=req.workspace_id,
            user_id=req.user_id,
            app_slug=req.app_slug,
        )
        return coding_environment_pb2.GetAccessResponse(access=_access_to_pb(access))
