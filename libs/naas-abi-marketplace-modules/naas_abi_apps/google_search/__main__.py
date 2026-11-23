"""``python -m naas_abi_apps.google_search``: run the module until it is stopped.

Configuration: ``GOOGLE_SEARCH_<FIELD>`` (e.g. ``GOOGLE_SEARCH_CHAT_MODEL``,
``GOOGLE_SEARCH_API_KEY_SECRET``), see ``naas_abi_apps.common.runtime``.
"""

from __future__ import annotations

import sys

from naas_abi_apps.common.runtime import main
from naas_abi_apps.google_search import ABIModule

ENV_PREFIX = "GOOGLE_SEARCH"

if __name__ == "__main__":
    sys.exit(main(ABIModule, ENV_PREFIX))
