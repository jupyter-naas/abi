"""``python -m naas_abi_apps.agicap``: run the module until it is stopped.

Configuration: ``AGICAP_<FIELD>`` (e.g. ``AGICAP_CHAT_MODEL``,
``AGICAP_API_TOKEN_SECRET``), see ``naas_abi_apps.common.runtime``.
"""

from __future__ import annotations

import sys

from naas_abi_apps.agicap import ABIModule
from naas_abi_apps.common.runtime import main

ENV_PREFIX = "AGICAP"

if __name__ == "__main__":
    sys.exit(main(ABIModule, ENV_PREFIX))
