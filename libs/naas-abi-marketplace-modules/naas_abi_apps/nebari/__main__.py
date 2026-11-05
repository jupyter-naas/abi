"""``python -m naas_abi_apps.nebari``: run the module until it is stopped.

Configuration: ``NEBARI_CHAT_MODEL``, see ``naas_abi_apps.common.runtime``.
"""

from __future__ import annotations

import sys

from naas_abi_apps.common.runtime import main
from naas_abi_apps.nebari import ABIModule

ENV_PREFIX = "NEBARI"

if __name__ == "__main__":
    sys.exit(main(ABIModule, ENV_PREFIX))
