"""``python -m naas_abi_apps.powerpoint``: run the module until it is stopped.

Configuration: ``POWERPOINT_<FIELD>`` (e.g. ``POWERPOINT_CHAT_MODEL``,
``POWERPOINT_TEMPLATE_PATH``), see ``naas_abi_apps.common.runtime``.
"""

from __future__ import annotations

import sys

from naas_abi_apps.common.runtime import main
from naas_abi_apps.powerpoint import ABIModule

ENV_PREFIX = "POWERPOINT"

if __name__ == "__main__":
    sys.exit(main(ABIModule, ENV_PREFIX))
