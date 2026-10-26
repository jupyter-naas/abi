"""IAM: principals, policies and the authorization every kernel service asks.

See ``AGENTS.md`` here.
"""

from naas_abi_core.services.iam.IAMPorts import (
    PermissionDeniedError,
    ResourceNotFoundError,
)

__all__ = ["PermissionDeniedError", "ResourceNotFoundError"]
