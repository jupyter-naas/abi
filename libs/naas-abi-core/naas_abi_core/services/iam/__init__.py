"""IAM: principals, policies and the authorization every kernel service asks.

See ``AGENTS.md`` here and docs/specs/rfcs/20261013_identity-and-authorization.md.
"""

from naas_abi_core.services.iam.IAMPorts import (
    PermissionDeniedError,
    ResourceNotFoundError,
)

__all__ = ["PermissionDeniedError", "ResourceNotFoundError"]
