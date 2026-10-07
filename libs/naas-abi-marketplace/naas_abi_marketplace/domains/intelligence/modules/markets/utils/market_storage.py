"""Where a market's files live in the datastore.

    <datastore_path>/<MarketFolder>/<MarketFolder>.yaml          the market as curated
    <datastore_path>/<MarketFolder>/<MarketFolder>.ttl           the graph built from it
    <datastore_path>/<MarketFolder>/yahoofinance/<SYMBOL>.json   quotes competitors were read from

The folder is the market label in PascalCase, as organizations are filed
(``intelligence/organizations/AirFranceKLM``): "Cloud Computing" -> ``CloudComputing``.
"""

from __future__ import annotations

import re

import yaml
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from rdflib import Graph


def market_folder(label: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", label)
    return "".join(w[:1].upper() + w[1:] for w in words) or "Unknown"


def market_prefix(datastore_path: str, label: str) -> str:
    return f"{datastore_path}/{market_folder(label)}"


def read_market_spec(
    storage: ObjectStorageService, datastore_path: str, folder: str
) -> dict:
    content = storage.get_object(f"{datastore_path}/{folder}", f"{folder}.yaml")
    return yaml.safe_load(content.decode("utf-8"))


def write_market_graph(
    storage: ObjectStorageService, datastore_path: str, label: str, graph: Graph
) -> str:
    folder = market_folder(label)
    prefix = f"{datastore_path}/{folder}"
    storage.put_object(
        prefix, f"{folder}.ttl", graph.serialize(format="turtle").encode()
    )
    return f"{prefix}/{folder}.ttl"
