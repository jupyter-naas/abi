"""Every account of the platform (Platform Settings > Users, ``services/accounts``).

An account is a platform resource, ``abi:nexus:user/<Nexus user id>`` (``-`` for
the list and for someone not invited yet). No role reaches it: the platform admin
holds these, or whoever a policy grants them to. Each change is also IAM's own
inside (``iam:SuspendPrincipal``, ``iam:ResumePrincipal``, ``iam:DeletePrincipal``,
``builtin.platform_admin``'s attachment) and the identity provider's
(``identity:ProvisionUser``, ``UpdateProvisionedUser``, ``DeleteProvisionedUser``),
asked as the caller.
"""

from naas_abi.apps.nexus.apps.api.app.services.iam.catalog.dsl import action, rtype

TYPES = (rtype("user", platform=True, description="An account of the platform."),)

ACTIONS = (
    action("ListUsers", "list", "user", description="List every account of the platform."),
    action("InviteUser", "admin", "user", description="Invite someone to the platform."),
    action(
        "UpdateUser",
        "admin",
        "user",
        description="Rename an account, or make it a platform admin or not.",
    ),
    action(
        "SuspendUser",
        "admin",
        "user",
        description="Deactivate an account: no sign-in, no API call; data and memberships stay.",
    ),
    action("ResumeUser", "admin", "user", description="Reactivate a deactivated account."),
    action(
        "DeleteUser",
        "admin",
        "user",
        description=(
            "Delete an account: at the identity provider, in IAM, its sessions and keys; "
            "what the person wrote stays."
        ),
    ),
)
