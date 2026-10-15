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


class NotFound(ServiceError, LookupError):
    """Generic not-found, IAM's own records included."""


class Conflict(ServiceError):
    """A taken name or identity, an attached or a managed policy (IAM)."""


class RevisionConflict(ServiceError):
    """A policy changed since the revision an update was based on (IAM)."""


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
    "NOT_FOUND": NotFound,
    "CONFLICT": Conflict,
    "REVISION_CONFLICT": RevisionConflict,
}


def domain_error(error: RPCError) -> ServiceError:
    return ERRORS.get(error.code, ServiceError)(
        error.code, str(error), response=error.response
    )
