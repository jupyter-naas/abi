"""``python -m naas_abi_apps.algolia``: run the module until it is stopped.

Configuration: ``ALGOLIA_<FIELD>`` (e.g. ``ALGOLIA_CHAT_MODEL``), see
``naas_abi_apps.common.runtime``.
"""

from __future__ import annotations

import sys

from naas_abi_apps.algolia import ABIModule
from naas_abi_apps.common.runtime import main

ENV_PREFIX = "ALGOLIA"

if __name__ == "__main__":
    sys.exit(main(ABIModule, ENV_PREFIX))
