"""Re-export of the demo source loaders.

The published person files belong to the people module
(``intelligence/modules/people/data/demo/person``); ``sources_to_employees``
reads the personnel module's own files (``personnel/data/demo/person``). This
module stays so cockpit imports keep working; import from those modules in new
code.
"""

from __future__ import annotations

from naas_abi_marketplace.domains.intelligence.modules.people.utils.person_sources import (
    SOURCE_DIR,
    load_person_sources,
    sources_to_experiences,
    sources_to_profile_urls,
)
from naas_abi_marketplace.domains.personnel.scripts.demo_graph import (
    sources_to_employees,
)

__all__ = [
    "SOURCE_DIR",
    "load_person_sources",
    "sources_to_employees",
    "sources_to_experiences",
    "sources_to_profile_urls",
]
