"""IRIs of Nexus identity individuals, derived from Postgres ids.

Shared by the boot-time graph builder, the runtime identity events and the
read-side resolver, so an event published today links to the same individuals
the graph rebuilt at the next boot contains. Memberships and access roles are
keyed by the (scope, user) pair: an event can name them without a lookup.
"""

from __future__ import annotations

from urllib.parse import quote

from rdflib import Namespace, URIRef

NEXUS = Namespace("http://ontology.naas.ai/nexus/")


def _iri(kind: str, *keys: str) -> URIRef:
    return URIRef(f"{NEXUS}{kind}/" + "/".join(quote(str(key), safe="") for key in keys))


def person_iri(user_id: str) -> URIRef:
    # One person per account until Nexus can merge accounts (SSO, several emails).
    return _iri("person", user_id)


def user_account_iri(user_id: str) -> URIRef:
    return _iri("user", user_id)


def superadmin_role_iri(user_id: str) -> URIRef:
    return _iri("superadmin-role", user_id)


def organization_iri(organization_id: str) -> URIRef:
    return _iri("organization", organization_id)


def organization_profile_iri(organization_id: str) -> URIRef:
    return _iri("organization-profile", organization_id)


def organization_membership_iri(organization_id: str, user_id: str) -> URIRef:
    return _iri("organization-membership", organization_id, user_id)


def organization_role_iri(organization_id: str, user_id: str) -> URIRef:
    return _iri("organization-role", organization_id, user_id)


def workspace_iri(workspace_id: str) -> URIRef:
    return _iri("workspace", workspace_id)


def workspace_membership_iri(workspace_id: str, user_id: str) -> URIRef:
    return _iri("workspace-membership", workspace_id, user_id)


def workspace_role_iri(workspace_id: str, user_id: str) -> URIRef:
    return _iri("workspace-role", workspace_id, user_id)


def workspace_app_iri(workspace_id: str, app_id: str) -> URIRef:
    return _iri("workspace-app", workspace_id, app_id)


def workspace_agent_iri(agent_config_id: str) -> URIRef:
    return _iri("workspace-agent", agent_config_id)


def deployment_site_iri(host: str) -> URIRef:
    return _iri("deployment", host)


def platform_configuration_iri(host: str) -> URIRef:
    return _iri("platform-configuration", host)


def tenant_branding_iri(host: str) -> URIRef:
    return _iri("tenant-branding", host)


def configuration_setting_iri(host: str, key: str) -> URIRef:
    return _iri("setting", host, key)


def feature_iri(feature_key: str) -> URIRef:
    return _iri("feature", feature_key)


def feature_policy_iri(role: str, organization_id: str | None = None) -> URIRef:
    if organization_id:
        return _iri("feature-policy", organization_id, role)
    return _iri("feature-policy", role)


def feature_override_iri(workspace_id: str, feature_key: str) -> URIRef:
    return _iri("feature-override", workspace_id, feature_key)


def process_iri(kind: str, *keys: str) -> URIRef:
    return _iri(kind, *keys)


def instant_iri(iso_timestamp: str) -> URIRef:
    return _iri("instant", iso_timestamp)
