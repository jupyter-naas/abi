"""JSON codec for `LogProcess` events.

Serializes onto2py-generated `RDFEntity` subclass instances to a JSON document
that round-trips back to a typed Python instance and remains convertible to
RDF — even if the Python class definition drifts after the event was stored.

The stored document carries three metadata keys alongside the event's data
fields:

- ``_uri``           — instance IRI
- ``_class_uri``     — class IRI (acts as the event type)
- ``_property_uris`` — snapshot of the field-name → predicate-IRI mapping
                       at publish-time. This is the schema-stability anchor:
                       Python field names can be renamed freely as long as
                       predicate IRIs stay stable; reconstruction uses the
                       *stored* `_property_uris`, not the live class's.

Nested `RDFEntity` instances are recursively embedded in the same shape, so
the whole reachable subgraph round-trips.
"""

from __future__ import annotations

import datetime
import json
from typing import Any

# Sentinel keys reserved by the codec
_META_KEYS = {"_uri", "_class_uri", "_property_uris"}


def _looks_like_entity(obj: Any) -> bool:
    """An RDFEntity has both `_uri` and `_class_uri`."""
    return hasattr(obj, "_uri") and hasattr(obj, "_class_uri")


def _coerce_for_json(value: Any) -> Any:
    """Make a value JSON-serializable (handles datetime, etc.)."""
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    return value


def to_event_dict(entity: Any) -> dict:
    """Serialize an `RDFEntity` (or subclass) to a JSON-safe dict.

    Recursively embeds nested entities. Public data fields come from
    Pydantic's `model_dump` (mode='json'), but raw attributes are inspected
    so that nested entities are detected even when Pydantic would have
    flattened them via custom serializers.
    """
    if not _looks_like_entity(entity):
        return _coerce_for_json(entity)

    out: dict[str, Any] = {
        "_uri": entity._uri,
        "_class_uri": str(entity._class_uri),
        "_property_uris": dict(getattr(entity, "_property_uris", {})),
    }

    model_fields = getattr(type(entity), "model_fields", {})
    for field_name in model_fields:
        if field_name.startswith("_") or field_name in _META_KEYS:
            continue
        raw = getattr(entity, field_name, None)
        if raw is None:
            out[field_name] = None
        elif _looks_like_entity(raw):
            out[field_name] = to_event_dict(raw)
        elif isinstance(raw, list):
            out[field_name] = [
                to_event_dict(item) if _looks_like_entity(item) else _coerce_for_json(item)
                for item in raw
            ]
        else:
            out[field_name] = _coerce_for_json(raw)
    return out


def serialize(entity: Any) -> bytes:
    """Encode an entity as a JSON UTF-8 byte string for storage."""
    return json.dumps(to_event_dict(entity), separators=(",", ":")).encode("utf-8")


def from_event_dict(data: dict, hint_class: type | None = None) -> Any:
    """Reconstruct a Pydantic instance from a dict produced by `to_event_dict`.

    Uses ``hint_class`` if provided, otherwise looks up the class by
    ``_class_uri`` via the LogProcess subclass index. Unknown fields in the
    JSON are silently dropped (forward-compat with class field removal);
    known fields missing from the JSON are left at their model default.
    """
    # Late import to avoid circular import with EventService.
    from naas_abi_core.services.event.ontologies.modules.EventOntology import LogProcess

    class_uri = data.get("_class_uri")
    if hint_class is not None:
        cls = hint_class
    else:
        cls = _resolve_class_by_uri(class_uri) or LogProcess

    model_fields = getattr(cls, "model_fields", {})
    kwargs: dict[str, Any] = {}
    for k, v in data.items():
        if k in _META_KEYS:
            continue
        if k not in model_fields:
            # Drop fields that no longer exist on the class.
            continue
        if isinstance(v, dict) and "_uri" in v and "_class_uri" in v:
            kwargs[k] = from_event_dict(v)
        elif isinstance(v, list) and v and isinstance(v[0], dict) and "_uri" in v[0]:
            kwargs[k] = [from_event_dict(item) for item in v]
        else:
            kwargs[k] = v

    uri = data.get("_uri") or ""
    try:
        return cls(_uri=uri, **kwargs)
    except Exception:
        # Permissive fallback if validation rejects (e.g. type changed).
        model_construct = getattr(cls, "model_construct", None)
        if model_construct is None:
            raise
        return model_construct(_fields_set=set(kwargs.keys()), _uri=uri, **kwargs)


def deserialize(payload: bytes, hint_class: type | None = None) -> Any:
    """Decode a stored JSON payload back into a typed instance."""
    return from_event_dict(json.loads(payload.decode("utf-8")), hint_class=hint_class)


def _resolve_class_by_uri(class_uri: str | None) -> type | None:
    """Walk LogProcess.__subclasses__() to find a class by its `_class_uri`."""
    if not class_uri:
        return None
    from naas_abi_core.services.event.ontologies.modules.EventOntology import LogProcess

    seen: set[type] = set()

    def walk(cls: type) -> type | None:
        if cls in seen:
            return None
        seen.add(cls)
        if str(getattr(cls, "_class_uri", "")) == class_uri:
            return cls
        for sub in cls.__subclasses__():
            found = walk(sub)
            if found is not None:
                return found
        return None

    return walk(LogProcess)
