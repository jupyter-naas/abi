"""Shared helpers for the personnel domain module."""

from naas_abi_marketplace.domains.personnel.utils.individual_uri import (
    DEMO_UUID_NS,
    PERSONNEL_ONTOLOGY,
    compact_personnel,
    personnel_individual_uri,
    uuid_part,
)

__all__ = [
    "DEMO_UUID_NS",
    "PERSONNEL_ONTOLOGY",
    "compact_personnel",
    "personnel_individual_uri",
    "uuid_part",
]
