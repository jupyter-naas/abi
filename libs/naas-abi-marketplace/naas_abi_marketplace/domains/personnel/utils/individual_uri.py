"""UUID-based individual IRIs under the personnel ontology namespace."""

from __future__ import annotations

import uuid

PERSONNEL_ONTOLOGY = "http://ontology.naas.ai/personnel/"
DEMO_UUID_NS = uuid.UUID("f47ac10b-58cc-4372-a567-0e02b2c3d479")


def personnel_individual_uri(seed: str | None = None) -> str:
    """Return ``{namespace}{uuid}``. *seed* yields a stable uuid5 (demo / idempotent writes)."""
    if seed:
        return f"{PERSONNEL_ONTOLOGY}{uuid.uuid5(DEMO_UUID_NS, seed)}"
    return f"{PERSONNEL_ONTOLOGY}{uuid.uuid4()}"


def uuid_part(uri: str | None) -> str | None:
    if not uri:
        return None
    tail = str(uri).rstrip("/").split("/")[-1]
    try:
        uuid.UUID(tail)
    except ValueError:
        return tail
    return tail


def compact_personnel(uri: str | None) -> str | None:
    part = uuid_part(uri)
    if not part:
        return None
    return f"personnel:{part}"
