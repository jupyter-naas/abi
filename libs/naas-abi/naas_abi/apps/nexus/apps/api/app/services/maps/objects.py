"""Maps objects in the platform's object storage: layer GeoJSON and feed logos.

Keys always come from a stored record (``MapsFeedLayer.storage_path``,
``MapsLayout.logo_path``), never from a request (see storage_keys.py).
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

# Feed logos are drawn in the sidebar and on every pin: keep them small.
MAX_LOGO_BYTES = 512_000


class MapsObjectMissingError(LookupError):
    """The record names an object the environment has not published."""


class MapsObjectInvalidError(ValueError):
    """The object exists but is not what the record expects."""


class MapsObjectStorePort(ABC):
    @abstractmethod
    def read(self, key: str) -> bytes:
        """The object's bytes; ``MapsObjectMissingError`` when it is not there."""


def layer_features(raw: bytes, class_labels: tuple[str, ...]) -> dict[str, Any]:
    """The layer's FeatureCollection: every feature, or those of its feature types."""
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise MapsObjectInvalidError(f"not JSON ({exc})") from exc
    if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
        raise MapsObjectInvalidError("not a GeoJSON FeatureCollection")
    features = [f for f in data.get("features") or [] if isinstance(f, dict)]
    if class_labels:
        kept = set(class_labels)
        features = [f for f in features if kept & _feature_types(f)]
    # Collection-level metadata (e.g. ``mapRegions``, ``observation_date``) is kept.
    return {**data, "type": "FeatureCollection", "features": features, "count": len(features)}


def _feature_types(feature: dict[str, Any]) -> set[str]:
    properties = feature.get("properties") or {}
    labels = properties.get("classLabels")
    types = {str(v) for v in labels} if isinstance(labels, list) else set()
    if properties.get("classLabel"):
        types.add(str(properties["classLabel"]))
    return types
