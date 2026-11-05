"""``python -m naas_abi_apps.sendgrid``: run the module until it is stopped.

Configuration: ``SENDGRID_<FIELD>`` (e.g. ``SENDGRID_CHAT_MODEL``), see
``naas_abi_apps.common.runtime``.
"""

from __future__ import annotations

import sys

from naas_abi_apps.common.runtime import main
from naas_abi_apps.sendgrid import ABIModule

ENV_PREFIX = "SENDGRID"

if __name__ == "__main__":
    sys.exit(main(ABIModule, ENV_PREFIX))
