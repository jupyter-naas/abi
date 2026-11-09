"""``python -m naas_abi_apps.pennylane``: run the module until it is stopped.

Configuration from the environment: ``PENNYLANE_API_KEY_SECRET``,
``PENNYLANE_DATASTORE_PATH``, ``PENNYLANE_CHAT_MODEL`` (see
``naas_abi_apps.common.runtime`` for the connection variables).
"""

from __future__ import annotations

import sys

from naas_abi_apps.common.runtime import main
from naas_abi_apps.pennylane import ABIModule

ENV_PREFIX = "PENNYLANE"

if __name__ == "__main__":
    sys.exit(main(ABIModule, ENV_PREFIX))
