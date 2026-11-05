"""``python -m naas_abi_apps.yahoofinance``: run the module until it is stopped.

Configuration: ``YAHOOFINANCE_<FIELD>`` (e.g. ``YAHOOFINANCE_CHAT_MODEL``,
``YAHOOFINANCE_DATASTORE_PATH``), see ``naas_abi_apps.common.runtime``.
"""

from __future__ import annotations

import sys

from naas_abi_apps.common.runtime import main
from naas_abi_apps.yahoofinance import ABIModule

ENV_PREFIX = "YAHOOFINANCE"

if __name__ == "__main__":
    sys.exit(main(ABIModule, ENV_PREFIX))
