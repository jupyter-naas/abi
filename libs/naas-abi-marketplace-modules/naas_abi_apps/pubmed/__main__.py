"""``python -m naas_abi_apps.pubmed``: run the module until it is stopped.

Configuration: ``PUBMED_<FIELD>`` (e.g. ``PUBMED_CHAT_MODEL``,
``PUBMED_DATASTORE_PATH``), see ``naas_abi_apps.common.runtime``.
"""

from __future__ import annotations

import sys

from naas_abi_apps.common.runtime import main
from naas_abi_apps.pubmed import ABIModule

ENV_PREFIX = "PUBMED"

if __name__ == "__main__":
    sys.exit(main(ABIModule, ENV_PREFIX))
