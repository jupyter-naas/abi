"""Identity over NATS: ``abi.identity.v1.<operation>`` (proto ``identity/v1``).

Each request runs under the ``CallContext`` built from its verified
credentials (``nats_rpc.authenticate_request``), so ``IdentityService``
authorizes the caller with the ``identity:*`` catalog, never this adapter.
"""

from __future__ import annotations

from functools import partial
from typing import Any

import nats
from google.protobuf.message import DecodeError
from naas_abi_proto.common.v1 import common_pb2
from naas_abi_proto.identity.v1 import identity_pb2 as pb

from naas_abi_core import logger
from naas_abi_core.engine.nats_dispatch import DomainRPCDispatcher
from naas_abi_core.engine.nats_rpc import (
    RequestPayloadError,
    authenticate_request,
    request_payload,
    respond_protobuf,
)
from naas_abi_core.engine.nats_sessions import ServicePrimary
from naas_abi_core.engine.nats_tracing import TracedService, add_traced_service
from naas_abi_core.services.identity.adapters import identity_nats_codec as codec
from naas_abi_core.services.identity.IdentityService import IdentityService


def _opt(message: Any, field: str) -> Any:
    return getattr(message, field) if message.HasField(field) else None


class IdentityPrimaryAdapterNATS(ServicePrimary):
    def __init__(self, service: IdentityService, jwt_secret: str) -> None:
        self._identity = service
        self._jwt_secret = jwt_secret
        self._dispatch = DomainRPCDispatcher(codec.SERVICE_NAME)
        self._service: TracedService | None = None

    async def start(self, nc: nats.NATS) -> None:
        if self._service is not None:
            return
        service = await add_traced_service(
            nc,
            name=codec.SERVICE_NAME,
            version=codec.SERVICE_VERSION,
            description="ABI kernel identity: OIDC providers, exposed over NATS RPC (v1).",
        )
        for operation in codec.OPERATIONS:
            await service.add_endpoint(
                name=operation,
                subject=f"{codec.SUBJECT_PREFIX}.{operation}",
                handler=partial(self._handle, operation=operation),
            )
        self._service = service

    async def stop(self) -> None:
        service, self._service = self._service, None
        try:
            if service is not None:
                await service.stop()
        finally:
            self._dispatch.close()

    async def _handle(self, request, *, operation: str) -> None:
        name = codec.OPERATIONS[operation]
        response_type = getattr(pb, f"{name}Response")
        caller = await authenticate_request(request, self._jwt_secret, response_type)
        if caller is None:
            return
        try:
            parsed = getattr(pb, f"{name}Request").FromString(
                await request_payload(request)
            )
            call = getattr(self, f"_call_{operation}")
            result = await self._dispatch.call(call, parsed, caller)
        except Exception as exc:  # noqa: BLE001 - translate at the RPC boundary
            code = codec.error_code(exc)
            if isinstance(exc, DecodeError):
                code = "INVALID_ARGUMENT"
            if isinstance(exc, RequestPayloadError):
                code = exc.code
            if code == "INTERNAL":
                logger.opt(exception=exc).error(f"identity NATS {operation} failed")
            result = response_type(
                error=common_pb2.CallError(
                    code=code,
                    message=codec.error_message(exc)
                    if code != "INTERNAL"
                    else "internal error",
                    retryable=code in {"INTERNAL", "UNAVAILABLE"},
                )
            )
        await respond_protobuf(request, result, response_type)

    # -- providers --------------------------------------------------------------

    def _call_list_providers(
        self, req: pb.ListProvidersRequest
    ) -> pb.ListProvidersResponse:
        return pb.ListProvidersResponse(
            providers=[
                codec.provider_to_pb(p) for p in self._identity.list_providers()
            ],
            default_provider=self._identity.default_provider,
        )

    def _call_get_provider(self, req: pb.GetProviderRequest) -> pb.GetProviderResponse:
        info = self._identity.get_provider(req.name)
        return pb.GetProviderResponse(provider=codec.provider_to_pb(info))

    # -- tokens -----------------------------------------------------------------

    def _call_verify_token(self, req: pb.VerifyTokenRequest) -> pb.VerifyTokenResponse:
        token = self._identity.verify_token(req.token, nonce=_opt(req, "nonce"))
        return pb.VerifyTokenResponse(token=codec.token_to_pb(token))

    def _call_authenticate(
        self, req: pb.AuthenticateRequest
    ) -> pb.AuthenticateResponse:
        user = self._identity.authenticate(req.token, nonce=_opt(req, "nonce"))
        return pb.AuthenticateResponse(user=codec.user_to_pb(user))

    # -- a relying party's sign-in ----------------------------------------------

    def _call_authorization_url(
        self, req: pb.AuthorizationUrlRequest
    ) -> pb.AuthorizationUrlResponse:
        url = self._identity.authorization_url(
            req.provider,
            redirect_uri=req.redirect_uri,
            state=req.state,
            nonce=req.nonce,
            code_challenge=req.code_challenge,
            login_hint=_opt(req, "login_hint"),
            prompt=_opt(req, "prompt"),
        )
        return pb.AuthorizationUrlResponse(url=url)

    def _call_exchange_code(
        self, req: pb.ExchangeCodeRequest
    ) -> pb.ExchangeCodeResponse:
        sign_in = self._identity.exchange_code(
            req.provider,
            code=req.code,
            code_verifier=req.code_verifier,
            redirect_uri=req.redirect_uri,
            nonce=req.nonce,
        )
        return pb.ExchangeCodeResponse(sign_in=codec.sign_in_to_pb(sign_in))

    def _call_refresh(self, req: pb.RefreshRequest) -> pb.RefreshResponse:
        sign_in = self._identity.refresh(
            req.provider, refresh_token=req.refresh_token, principal_id=req.principal_id
        )
        return pb.RefreshResponse(sign_in=codec.sign_in_to_pb(sign_in))

    def _call_revoke(self, req: pb.RevokeRequest) -> pb.RevokeResponse:
        revoked = self._identity.revoke(req.provider, refresh_token=req.refresh_token)
        return pb.RevokeResponse(revoked=revoked)

    def _call_end_session_url(
        self, req: pb.EndSessionUrlRequest
    ) -> pb.EndSessionUrlResponse:
        url = self._identity.end_session_url(
            req.provider,
            id_token_hint=_opt(req, "id_token_hint"),
            post_logout_redirect_uri=_opt(req, "post_logout_redirect_uri"),
            state=_opt(req, "state"),
        )
        return pb.EndSessionUrlResponse(url=url)
