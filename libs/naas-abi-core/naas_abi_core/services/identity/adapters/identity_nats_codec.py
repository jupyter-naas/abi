"""Identity records and errors on the wire (``naas_abi_proto/identity/v1``).

Shared by the NATS primary and the NATS client, so neither imports the other.
"""

from __future__ import annotations

import json
from typing import Any

from naas_abi_proto.identity.v1 import identity_pb2 as pb

from naas_abi_core.services.iam.IAMPorts import (
    PermissionDeniedError,
    ResourceNotFoundError,
)
from naas_abi_core.services.identity.IdentityPorts import (
    AuthenticatedUser,
    IdentityError,
    PrincipalSuspendedError,
    ProviderInfo,
    ProviderUnavailableError,
    ProvisionedUser,
    ProvisioningError,
    SignIn,
    SignInError,
    TokenRejectedError,
    TokenSet,
    UnknownProviderError,
    VerifiedToken,
)

SUBJECT_PREFIX = "abi.identity.v1"
SERVICE_NAME = "identity"
SERVICE_VERSION = "1.0.0"

# Operation (subject suffix) -> message name, one per Request/Response pair.
OPERATIONS = {
    "list_providers": "ListProviders",
    "get_provider": "GetProvider",
    "verify_token": "VerifyToken",
    "authenticate": "Authenticate",
    "authorization_url": "AuthorizationUrl",
    "exchange_code": "ExchangeCode",
    "refresh": "Refresh",
    "revoke": "Revoke",
    "end_session_url": "EndSessionUrl",
    "provision_user": "ProvisionUser",
    "find_provisioned_user": "FindProvisionedUser",
}


# -- errors ----------------------------------------------------------------------


def error_code(exc: BaseException) -> str:
    if isinstance(exc, TokenRejectedError):
        return f"TOKEN_{exc.reason.upper()}"
    if isinstance(exc, PermissionDeniedError):
        return "PERMISSION_DENIED"
    if isinstance(exc, (UnknownProviderError, ResourceNotFoundError)):
        return "NOT_FOUND"
    if isinstance(exc, IdentityError):
        return exc.code
    if isinstance(exc, NotImplementedError):
        return "UNIMPLEMENTED"
    if isinstance(exc, ValueError):
        return "INVALID_ARGUMENT"
    return "INTERNAL"


def error_message(exc: BaseException) -> str:
    if isinstance(exc, SignInError):
        # The OAuth error first, so the client gets it back as such.
        return f"{exc.error}: {exc.description}" if exc.description else exc.error
    if isinstance(exc, PrincipalSuspendedError):
        return f"{exc.principal_id} {exc.status}"
    return str(exc)


def raise_for(error: Any) -> None:
    """Raise the exception a ``CallError`` stands for."""
    code, message = error.code, error.message
    if code.startswith("TOKEN_"):
        raise TokenRejectedError(code.removeprefix("TOKEN_").lower(), message)
    if code == "PERMISSION_DENIED":
        raise PermissionDeniedError(message=message)
    if code == "NOT_FOUND":
        raise UnknownProviderError(message)
    if code == "SUSPENDED":
        principal_id, _, status = message.partition(" ")
        raise PrincipalSuspendedError(principal_id, status or "suspended")
    if code == "SIGN_IN_FAILED":
        oauth_error, _, description = message.partition(": ")
        raise SignInError(oauth_error, description or None)
    if code == "UNAVAILABLE":
        raise ProviderUnavailableError(message)
    if code == "INVALID_ARGUMENT":
        raise ValueError(message)
    if code == "UNIMPLEMENTED":
        raise NotImplementedError(message)
    if code == "PROVISIONING_FAILED":
        raise ProvisioningError(message)
    raise RuntimeError(f"identity NATS RPC failed ({code}): {message}")


# -- records ---------------------------------------------------------------------


def provider_to_pb(info: ProviderInfo) -> pb.Provider:
    return pb.Provider(
        name=info.name,
        issuer=info.issuer,
        client_id=info.client_id,
        display_name=info.display_name,
        scopes=list(info.scopes),
        groups_claim=info.groups_claim,
        provisioning=info.provisioning,
    )


def provider_from_pb(message: pb.Provider) -> ProviderInfo:
    return ProviderInfo(
        name=message.name,
        issuer=message.issuer,
        client_id=message.client_id,
        display_name=message.display_name,
        scopes=tuple(message.scopes),
        groups_claim=message.groups_claim if message.HasField("groups_claim") else None,
        provisioning=message.provisioning,  # type: ignore[arg-type]
    )


def provisioned_to_pb(user: ProvisionedUser) -> pb.ProvisionedUser:
    return pb.ProvisionedUser(
        provider=user.provider,
        email=user.email,
        subject=user.subject,
        name=user.name,
        created=user.created,
        disabled=user.disabled,
    )


def provisioned_from_pb(message: pb.ProvisionedUser) -> ProvisionedUser:
    return ProvisionedUser(
        provider=message.provider,
        email=message.email,
        subject=message.subject if message.HasField("subject") else None,
        name=message.name if message.HasField("name") else None,
        created=message.created,
        disabled=message.disabled,
    )


def token_to_pb(token: VerifiedToken) -> pb.VerifiedToken:
    return pb.VerifiedToken(
        provider=token.provider,
        issuer=token.issuer,
        subject=token.subject,
        audience=list(token.audience),
        issued_at=token.issued_at,
        expires_at=token.expires_at,
        email=token.email,
        email_verified=token.email_verified,
        display_name=token.display_name,
        groups=list(token.groups),
        nonce=token.nonce,
        session_id=token.session_id,
        claims_json=json.dumps(dict(token.claims), default=str),
    )


def _opt(message: Any, field: str) -> Any:
    return getattr(message, field) if message.HasField(field) else None


def token_from_pb(message: pb.VerifiedToken) -> VerifiedToken:
    return VerifiedToken(
        provider=message.provider,
        issuer=message.issuer,
        subject=message.subject,
        audience=tuple(message.audience),
        issued_at=message.issued_at,
        expires_at=message.expires_at,
        email=_opt(message, "email"),
        email_verified=message.email_verified,
        display_name=_opt(message, "display_name"),
        groups=tuple(message.groups),
        nonce=_opt(message, "nonce"),
        session_id=_opt(message, "session_id"),
        claims=json.loads(message.claims_json) if message.claims_json else {},
    )


def user_to_pb(user: AuthenticatedUser) -> pb.AuthenticatedUser:
    return pb.AuthenticatedUser(
        principal_id=user.principal_id,
        token=token_to_pb(user.token),
        group_ids=list(user.group_ids),
    )


def user_from_pb(message: pb.AuthenticatedUser) -> AuthenticatedUser:
    return AuthenticatedUser(
        principal_id=message.principal_id,
        token=token_from_pb(message.token),
        group_ids=tuple(message.group_ids),
    )


def sign_in_to_pb(sign_in: SignIn) -> pb.SignIn:
    tokens = sign_in.tokens
    return pb.SignIn(
        user=user_to_pb(sign_in.user),
        tokens=pb.TokenSet(
            id_token=tokens.id_token,
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            expires_in=tokens.expires_in,
            token_type=tokens.token_type,
            scope=tokens.scope,
        ),
        refresh_at=sign_in.refresh_at,
    )


def sign_in_from_pb(message: pb.SignIn) -> SignIn:
    tokens = message.tokens
    return SignIn(
        user=user_from_pb(message.user),
        tokens=TokenSet(
            id_token=_opt(tokens, "id_token"),
            access_token=_opt(tokens, "access_token"),
            refresh_token=_opt(tokens, "refresh_token"),
            expires_in=_opt(tokens, "expires_in"),
            token_type=_opt(tokens, "token_type"),
            scope=_opt(tokens, "scope"),
        ),
        refresh_at=message.refresh_at,
    )
