"""Canonical filesystem paths for the personnel module."""

from __future__ import annotations

from pathlib import Path

PERSONNEL_ROOT = Path(__file__).resolve().parent
ONTOLOGIES_DIR = PERSONNEL_ROOT / "ontologies"
COCKPIT_ROOT = PERSONNEL_ROOT / "apps" / "cockpit"
COCKPIT_DATA_ROOT = COCKPIT_ROOT / "data"  # structure reference copy; app reads ObjectStorage

# Demo inputs (LinkedIn-derived source JSON) — not served by the cockpit app.
DEMO_SOURCE_DIR = PERSONNEL_ROOT / "data" / "demo" / "person"

# Demo instance graph (TTL) — built from demo sources, consumed by export scripts.
DEMO_GRAPH_DIR = PERSONNEL_ROOT / "graphs" / "demo"
DEMO_GRAPH_FILE = DEMO_GRAPH_DIR / "personnel.ttl"


def module_configuration_class() -> type:
    from naas_abi_marketplace.domains.personnel import ABIModule

    return ABIModule.Configuration


def _configuration_default(field_name: str) -> str:
    field = module_configuration_class().model_fields[field_name]
    default = field.default
    if default is None or default is ...:
        raise ValueError(f"Missing default for personnel Configuration.{field_name}")
    return str(default)


def module_datastore_path() -> str:
    try:
        from naas_abi_marketplace.domains.personnel import ABIModule

        return ABIModule.get_instance().configuration.datastore_path
    except Exception:
        return _configuration_default("datastore_path")


def module_graph_name() -> str:
    try:
        from naas_abi_marketplace.domains.personnel import ABIModule

        return ABIModule.get_instance().configuration.graph_name
    except Exception:
        return _configuration_default("graph_name")


def module_ontology_namespace() -> str:
    try:
        from naas_abi_marketplace.domains.personnel import ABIModule

        return ABIModule.get_instance().configuration.ontology_namespace
    except Exception:
        return _configuration_default("ontology_namespace")


def cockpit_storage_prefix(datastore_path: str | None = None) -> str:
    """ObjectStorage prefix for cockpit runtime datasets."""
    path = datastore_path or module_datastore_path()
    return f"{path.rstrip('/')}/apps/cockpit/data"
