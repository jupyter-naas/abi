"""``python -m naas_abi_apps.naas``: run the module until it is stopped.

Configuration: ``NAAS_<FIELD>`` (e.g. ``NAAS_CHAT_MODEL``,
``NAAS_API_KEY_SECRET``), see ``naas_abi_apps.common.runtime``.
"""

from __future__ import annotations

import sys

from naas_abi_apps.common.runtime import main
from naas_abi_apps.naas import ABIModule

ENV_PREFIX = "NAAS"

if __name__ == "__main__":
    sys.exit(main(ABIModule, ENV_PREFIX))
