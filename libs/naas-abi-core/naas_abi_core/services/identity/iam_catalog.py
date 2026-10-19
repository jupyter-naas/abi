"""The ``identity`` action catalog: the configured OIDC providers.

A provider is a platform resource, ``abi:-:-:identity:provider/<name>``.
``Authenticate`` creates or refreshes the token's IAM user, as the engine, once
the caller is allowed it; ``SignIn`` runs the provider side of a relying
party's sign-in with the provider's client secret, which never leaves the
engine. A code exchange and a refresh also resolve (and may create) the user:
they need ``SignIn`` and ``Authenticate``.
"""

from __future__ import annotations

from naas_abi_core.services.iam.catalog import ActionCatalog, ActionSpec, ResourceType

SERVICE = "identity"
SUBJECT_PREFIX = "abi.identity.v1"


def _action(name: str, level: str, *subjects: str, description: str = "") -> ActionSpec:
    return ActionSpec(
        name=name,
        level=level,  # type: ignore[arg-type]
        resource_types=("provider",),
        subjects=tuple(f"{SUBJECT_PREFIX}.{s}" for s in subjects),
        description=description,
    )


CATALOG = ActionCatalog(
    service=SERVICE,
    # 2: ProvisionUser and FindProvisionedUser.
    version=2,
    resource_types=(
        ResourceType(
            "provider",
            id="opaque",
            placement="platform",
            description="A configured OIDC identity provider, by name.",
        ),
    ),
    actions=(
        _action("ListProviders", "list", "list_providers"),
        _action("GetProvider", "read", "get_provider"),
        _action(
            "VerifyToken",
            "read",
            "verify_token",
            description="Verify an ID token of the provider, with no side effect.",
        ),
        _action(
            "Authenticate",
            "write",
            "authenticate",
            description="Verify an ID token and resolve its IAM user, created on first sign-in.",
        ),
        _action(
            "SignIn",
            "write",
            "authorization_url",
            "exchange_code",
            "refresh",
            "revoke",
            "end_session_url",
            description=(
                "Run a relying party's sign-in at the provider, with its client secret. "
                "Exchanging a code or refreshing also needs identity:Authenticate."
            ),
        ),
        _action(
            "ProvisionUser",
            "admin",
            "provision_user",
            description=(
                "Make sure a person exists at the provider (an invitation's first "
                "step). Nexus checks the inviting person's rights, then calls as api."
            ),
        ),
        _action("FindProvisionedUser", "read", "find_provisioned_user"),
    ),
)
