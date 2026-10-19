"""``provisioning: none``: the provider's users are managed in the provider.

ABI never creates a user there. An invitation to such a provider is a pending
grant only: it attaches when the invited person signs in with that email
verified, and the provider (Okta, Entra, ...) is where their account is made.
"""

from __future__ import annotations

from naas_abi_core.services.identity.IdentityPorts import (
    ProvisionedUser,
    ProvisioningPort,
)


class ProvisioningNone(ProvisioningPort):
    def __init__(self, provider: str) -> None:
        self._provider = provider

    def ensure_user(self, email: str, *, name: str | None = None) -> ProvisionedUser:
        raise NotImplementedError(
            f"Users of provider {self._provider!r} are managed in the identity "
            "provider (provisioning: none)"
        )

    def find_user(self, email: str) -> ProvisionedUser | None:
        raise NotImplementedError(
            f"Users of provider {self._provider!r} are managed in the identity "
            "provider (provisioning: none)"
        )
