"""Portable domain failures; engine exception classes are not imported."""

from naas_abi_sdk.transport import RPCError


class ServiceError(RPCError):
    pass


class ObjectNotFound(ServiceError):
    pass


class ObjectAlreadyExists(ServiceError):
    pass


class DocumentNotFound(ServiceError):
    pass


class CollectionNotFound(ServiceError):
    pass


class VersionConflict(ServiceError):
    pass


class UniqueViolation(ServiceError):
    pass


class CacheNotFoundError(ServiceError):
    pass


class CacheExpiredError(ServiceError):
    pass


class KVNotFoundError(ServiceError):
    pass


class SecretAuthenticationError(ServiceError):
    pass


class PermissionDenied(ServiceError, PermissionError):
    """The caller can see the resource but may not perform the action (IAM §5.4)."""


class GrantNotHeld(PermissionDenied):
    """A change would give more than the caller holds (IAM, "Grant only what you
    hold"); the message names the statement, action and resource."""


class NotFound(ServiceError, LookupError):
    """Generic not-found, IAM's own records included."""


class Conflict(ServiceError):
    """A taken name or identity, an attached or a managed policy (IAM)."""


class RevisionConflict(ServiceError):
    """A policy changed since the revision an update was based on (IAM)."""


class TokenRejected(ServiceError):
    """An identity provider's token is not accepted; ``code`` is ``TOKEN_<REASON>``
    (``TOKEN_EXPIRED``, ``TOKEN_WRONG_AUDIENCE``, ``TOKEN_UNKNOWN_ISSUER``...)."""

    @property
    def reason(self) -> str:
        return self.code.removeprefix("TOKEN_").lower()


class Suspended(ServiceError):
    """IAM suspended or deleted the user a valid token names."""


class SignInFailed(ServiceError):
    """The identity provider refused a code exchange or a refresh."""


class ProviderUnavailable(ServiceError):
    """The identity provider cannot be reached."""


class ProvisioningFailed(ServiceError):
    """The identity provider's admin API refused or failed a provisioning call."""


class Unimplemented(ServiceError, NotImplementedError):
    """The provider's users are managed in the provider (``provisioning: none``)."""


ERRORS = {
    "OBJECT_NOT_FOUND": ObjectNotFound,
    "OBJECT_ALREADY_EXISTS": ObjectAlreadyExists,
    "DOCUMENT_NOT_FOUND": DocumentNotFound,
    "COLLECTION_NOT_FOUND": CollectionNotFound,
    "VERSION_CONFLICT": VersionConflict,
    "UNIQUE_VIOLATION": UniqueViolation,
    "CACHE_NOT_FOUND": CacheNotFoundError,
    "CACHE_EXPIRED": CacheExpiredError,
    "KV_NOT_FOUND": KVNotFoundError,
    "SECRET_AUTH_FAILED": SecretAuthenticationError,
    "PERMISSION_DENIED": PermissionDenied,
    "GRANT_NOT_HELD": GrantNotHeld,
    "NOT_FOUND": NotFound,
    "CONFLICT": Conflict,
    "REVISION_CONFLICT": RevisionConflict,
    "SUSPENDED": Suspended,
    "SIGN_IN_FAILED": SignInFailed,
    "UNAVAILABLE": ProviderUnavailable,
    "PROVISIONING_FAILED": ProvisioningFailed,
    "UNIMPLEMENTED": Unimplemented,
}


def domain_error(error: RPCError) -> ServiceError:
    if error.code.startswith("TOKEN_"):
        return TokenRejected(error.code, str(error), response=error.response)
    return ERRORS.get(error.code, ServiceError)(
        error.code, str(error), response=error.response
    )
