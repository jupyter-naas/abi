"""Re-export of the demo source loaders.

The demo person files belong to the people module
(``intelligence/modules/people/data/demo/person``); the HR roster reader is the
personnel demo's. This module stays so cockpit imports keep working; import
from those modules in new code.
"""

from __future__ import annotations

from naas_abi_marketplace.domains.intelligence.modules.people.person_sources import (
    SOURCE_DIR,
    load_person_sources,
    sources_to_experiences,
    sources_to_profile_urls,
)
from naas_abi_marketplace.domains.personnel.graph.demo import sources_to_employees

__all__ = [
    "SOURCE_DIR",
    "load_person_sources",
    "sources_to_employees",
    "sources_to_experiences",
    "sources_to_profile_urls",
]
