"""Workspace secrets, providers and ABI servers: the settings section."""

from naas_abi.apps.nexus.apps.api.app.services.iam.catalog.dsl import action, rtype

TYPES = (
    rtype("secret"),
    rtype("provider_model", platform=True),
    rtype("abi_server"),
)

ACTIONS = (
    # Masked values: listing never reveals a secret.
    action("ListSecrets", "list", "secret", feature="settings"),
    action("CreateSecret", "admin", "secret", feature="settings"),
    action("UpdateSecret", "admin", "secret", feature="settings"),
    action("DeleteSecret", "admin", "secret", feature="settings"),
    action("ImportSecrets", "admin", "secret", feature="settings"),
    action("ListProviderModels", "list", "provider_model"),
    action("GetProviderModel", "read", "provider_model"),
    action("UpdateProviderModel", "admin", "provider_model"),
    action("ListAbiServers", "list", "abi_server", feature="settings"),
    action("GetAbiServer", "read", "abi_server", feature="settings"),
    action("CreateAbiServer", "admin", "abi_server", feature="settings"),
    action("UpdateAbiServer", "admin", "abi_server", feature="settings"),
    action("DeleteAbiServer", "admin", "abi_server", feature="settings"),
)
