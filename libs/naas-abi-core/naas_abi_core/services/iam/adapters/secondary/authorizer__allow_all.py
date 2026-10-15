"""The ``allow_all`` authorizer: an explicit opt-out of authorization.

Selected only by ``services.iam.authorizer: allow_all``; never a default or a
fallback. It warns when it is built, so every boot that runs without
authorization says so.
"""

from __future__ import annotations

from collections.abc import Iterable

from naas_abi_core import logger
from naas_abi_core.engine.call_context import CallContext
from naas_abi_core.services.iam.IAMPorts import (
    Decision,
    Explanation,
    FilterResult,
    IAuthorizer,
)

WARNING = (
    "IAM authorizer 'allow_all': every call is allowed, policies are not "
    "enforced. Set services.iam.authorizer to 'policy' to enforce them."
)


class AllowAllAuthorizer(IAuthorizer):
    name = "allow_all"

    def __init__(self) -> None:
        logger.warning(WARNING)

    def check(self, ctx: CallContext, action: str, resource: str) -> Decision:
        return Decision(True, True, "allow")

    def filter(
        self, ctx: CallContext, action: str, resources: Iterable[str]
    ) -> FilterResult:
        return FilterResult(list(resources), [""])

    def explain(self, ctx: CallContext, action: str, resource: str) -> Explanation:
        return Explanation(True, "allow", action, resource)
