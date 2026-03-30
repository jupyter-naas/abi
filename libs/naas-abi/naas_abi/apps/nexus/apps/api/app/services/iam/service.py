from __future__ import annotations

import re
from dataclasses import dataclass

from naas_abi.apps.nexus.apps.api.app.services.iam.port import TokenData


@dataclass
class IAMPermissionError(PermissionError):
    scope: str

    def __str__(self) -> str:
        return f"missing_scope:{self.scope}"


class IAMService:
    def __init__(self, policy: object | None = None):
        self._policy = policy

    @staticmethod
    def _scope_matches(granted_scope: str, required_scope: str) -> bool:
        escaped = re.escape(granted_scope).replace("\\*", ".*")
        return re.fullmatch(escaped, required_scope) is not None

    def is_allowed(self, token_data: TokenData, required_scope: str) -> bool:
        if not token_data.is_authenticated or not token_data.user_id:
            return False
        if not token_data.scopes:
            return False
        return any(self._scope_matches(scope, required_scope) for scope in token_data.scopes)

    def ensure(self, token_data: TokenData, required_scope: str) -> None:
        if not self.is_allowed(token_data=token_data, required_scope=required_scope):
            raise IAMPermissionError(scope=required_scope)
