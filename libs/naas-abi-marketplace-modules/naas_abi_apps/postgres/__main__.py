"""``python -m naas_abi_apps.postgres``: run the module until it is stopped.

Configuration: ``POSTGRES_<FIELD>`` (e.g. ``POSTGRES_CHAT_MODEL``), see
``naas_abi_apps.common.runtime``.
"""

from __future__ import annotations

import sys

from naas_abi_apps.common.runtime import main
from naas_abi_apps.postgres import ABIModule

ENV_PREFIX = "POSTGRES"

if __name__ == "__main__":
    sys.exit(main(ABIModule, ENV_PREFIX))
