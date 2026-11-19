"""``python -m naas_abi_apps.sec_gov``: run the module until it is stopped.

Configuration: ``SEC_GOV_<FIELD>`` (e.g. ``SEC_GOV_USER_AGENT``,
``SEC_GOV_DATASTORE_PATH``), see ``naas_abi_apps.common.runtime``.
"""

from __future__ import annotations

import sys

from naas_abi_apps.common.runtime import main
from naas_abi_apps.sec_gov import ABIModule

ENV_PREFIX = "SEC_GOV"

if __name__ == "__main__":
    sys.exit(main(ABIModule, ENV_PREFIX))
