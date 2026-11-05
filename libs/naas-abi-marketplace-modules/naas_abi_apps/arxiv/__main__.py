"""``python -m naas_abi_apps.arxiv``: run the module until it is stopped.

Configuration: ``ARXIV_<FIELD>`` (e.g. ``ARXIV_CHAT_MODEL``,
``ARXIV_GRAPH_NAME``), see ``naas_abi_apps.common.runtime``.
"""

from __future__ import annotations

import sys

from naas_abi_apps.arxiv import ABIModule
from naas_abi_apps.common.runtime import main

ENV_PREFIX = "ARXIV"

if __name__ == "__main__":
    sys.exit(main(ABIModule, ENV_PREFIX))
