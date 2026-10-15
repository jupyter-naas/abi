"""The ``policy`` authorizer, the default: RFC §5 over IAM's own state."""

from __future__ import annotations

from collections.abc import Iterable

from naas_abi_core.engine.call_context import CallContext
from naas_abi_core.services.iam.evaluator import Evaluator
from naas_abi_core.services.iam.IAMPorts import (
    Decision,
    Explanation,
    FilterResult,
    IAuthorizer,
    PolicySource,
)


class PolicyAuthorizer(IAuthorizer):
    name = "policy"

    def __init__(self, source: PolicySource) -> None:
        self._evaluator = Evaluator(source)

    def check(self, ctx: CallContext, action: str, resource: str) -> Decision:
        return self._evaluator.check(ctx, action, resource)

    def filter(
        self, ctx: CallContext, action: str, resources: Iterable[str]
    ) -> FilterResult:
        return self._evaluator.filter(ctx, action, resources)

    def explain(self, ctx: CallContext, action: str, resource: str) -> Explanation:
        return self._evaluator.explain(ctx, action, resource)
