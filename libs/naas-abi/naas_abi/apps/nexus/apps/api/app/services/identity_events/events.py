"""Identity and access processes, as EventService events.

Each class is the event-log projection of a ``nexus:IdentityAndAccessProcess``
subclass from NexusPlatformOntology.ttl: same class IRI, same property IRIs.
The boot-time identity graph (services/identity_graph) holds the same processes
as individuals, so an event published at runtime and the graph agree on what a
``nexus:ChangeWorkspaceMemberRole`` is and which individuals it touched.

Two differences from the graph classes, both from ``LogProcess``:
- WHEN is ``abi:createdAt`` (an xsd:dateTime stamped by EventService), not
  ``nexus:createdAt`` → ``abi:TemporalInstant``.
- The actor is ``actor_user_id`` / ``actor_workspace_id`` / ``triggered_via``,
  stamped from the request; ``created_by`` carries the actor's person IRI.

Payloads hold ids and IRIs only. Names and emails stay in Postgres and the
identity graph.
"""

from __future__ import annotations

from typing import ClassVar

from naas_abi.ontologies.modules.NexusPlatformOntology import IdentityAndAccessProcess
from naas_abi_core.services.event.ontologies.modules.EventOntology import LogProcess

_NEXUS = "http://ontology.naas.ai/nexus/"

_OBJECT_FIELDS = ("created_by", "created_for", "creates", "updates", "deletes", "occurs_in")
_DATA_FIELDS = (
    "target_user_id",
    "target_workspace_id",
    "target_organization_id",
    "membership_role",
    "previous_membership_role",
    "changed_fields",
    "changes_json",
)


class NexusIdentityEvent(LogProcess):
    """nexus:IdentityAndAccessProcess, as an event."""

    _class_uri: ClassVar[str] = f"{_NEXUS}IdentityAndAccessProcess"
    _name: ClassVar[str] = "Identity and Access Process"
    # Taken from the generated ontology class so the IRIs cannot drift.
    _property_uris: ClassVar[dict] = {
        name: IdentityAndAccessProcess._property_uris[name]
        for name in (*_OBJECT_FIELDS, *_DATA_FIELDS)
    }
    _object_properties: ClassVar[set[str]] = set(_OBJECT_FIELDS)

    # WHO: persons, as IRIs (nexus:person/<user id>).
    created_by: list[str] | None = None
    created_for: list[str] | None = None
    # HOW WE KNOW: the records written, as IRIs.
    creates: list[str] | None = None
    updates: list[str] | None = None
    deletes: list[str] | None = None
    # WHERE: the deployment site.
    occurs_in: list[str] | None = None

    target_user_id: str | None = None
    target_workspace_id: str | None = None
    target_organization_id: str | None = None
    membership_role: str | None = None
    previous_membership_role: str | None = None
    changed_fields: list[str] | None = None
    changes_json: str | None = None


def _event_class(name: str, label: str) -> type[NexusIdentityEvent]:
    return type(
        f"{name}Event",
        (NexusIdentityEvent,),
        {
            "__module__": __name__,
            "__doc__": f"nexus:{name}, as an event.",
            "__annotations__": {"_class_uri": ClassVar[str], "_name": ClassVar[str]},
            "_class_uri": f"{_NEXUS}{name}",
            "_name": label,
        },
    )


_LABELS = {
    "CreateUser": "Create User",
    "UpdateUser": "Update User",
    "DeleteUser": "Delete User",
    "CreateOrganization": "Create Organization",
    "UpdateOrganization": "Update Organization",
    "DeleteOrganization": "Delete Organization",
    "AddUserToOrganization": "Add User to Organization",
    "ChangeOrganizationMemberRole": "Change Organization Member Role",
    "RemoveUserFromOrganization": "Remove User from Organization",
    "CreateWorkspace": "Create Workspace",
    "UpdateWorkspace": "Update Workspace",
    "DeleteWorkspace": "Delete Workspace",
    "AddUserToWorkspace": "Add User to Workspace",
    "ChangeWorkspaceMemberRole": "Change Workspace Member Role",
    "RemoveUserFromWorkspace": "Remove User from Workspace",
    "ConfigureWorkspaceApp": "Configure Workspace App",
    "ConfigureWorkspaceAgent": "Configure Workspace Agent",
    "ConfigureOrganizationRoleFeatures": "Configure Organization Role Features",
}

EVENT_CLASSES: dict[str, type[NexusIdentityEvent]] = {
    name: _event_class(name, label) for name, label in _LABELS.items()
}
