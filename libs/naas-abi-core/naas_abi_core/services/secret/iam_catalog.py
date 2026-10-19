"""secret's action catalog (RFC §6.4, "secret") and its seals (§11.3).

One ``secret/<key>`` per key, opaque, placed by key prefix. ``idp/`` keys are
the built-in IdP's and ``iam/`` keys the engine's, sealed in code: no policy
opens them to anyone else, wherever a placement puts them.
"""

from __future__ import annotations

from naas_abi_core.services.iam.catalog import (
    ActionCatalog,
    ResourceType,
    service_action,
)
from naas_abi_core.services.iam.IAMPorts import Seal

SERVICE = "secret"
SUBJECT_PREFIX = "abi.svc.secret.v1"
SECRET = "secret"


def _subject(name: str) -> str:
    return f"{SUBJECT_PREFIX}.{name}"


CATALOG = ActionCatalog(
    service=SERVICE,
    version=1,
    resource_types=(ResourceType(SECRET, id="opaque", description="A secret key."),),
    actions=(
        service_action("List", "list", (SECRET,), _subject("list")),
        service_action("Get", "read", (SECRET,), _subject("get")),
        service_action("Set", "write", (SECRET,), _subject("set")),
        service_action("Remove", "write", (SECRET,), _subject("remove")),
    ),
)

SEALS: tuple[Seal, ...] = (
    Seal("abi:*:*:secret:secret/idp%2F*", "idp"),
    Seal("abi:*:*:secret:secret/iam%2F*", "engine"),
)
