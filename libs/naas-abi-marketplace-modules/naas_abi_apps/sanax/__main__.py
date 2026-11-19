"""``python -m naas_abi_apps.sanax``: run the module until it is stopped.

Configuration: ``SANAX_<FIELD>`` (e.g. ``SANAX_CHAT_MODEL``,
``SANAX_GRAPH_NAME``), see ``naas_abi_apps.common.runtime``.
"""

from __future__ import annotations

import sys

from naas_abi_apps.common.runtime import main
from naas_abi_apps.sanax import ABIModule

ENV_PREFIX = "SANAX"

if __name__ == "__main__":
    sys.exit(main(ABIModule, ENV_PREFIX))
