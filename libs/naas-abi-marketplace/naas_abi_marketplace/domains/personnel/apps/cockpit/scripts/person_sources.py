"""Re-export of the domain-level demo source loader.

The loader moved to ``domains/personnel/person_sources.py`` when a second app
started reading the same ``data/demo/person/*/index.json`` files. This module
stays so cockpit imports keep working; import from the domain in new code.
"""

from __future__ import annotations

from naas_abi_marketplace.domains.personnel.person_sources import (
    SOURCE_DIR,
    load_person_sources,
    sources_to_employees,
    sources_to_experiences,
    sources_to_profile_urls,
)

__all__ = [
    "SOURCE_DIR",
    "load_person_sources",
    "sources_to_employees",
    "sources_to_experiences",
    "sources_to_profile_urls",
]
