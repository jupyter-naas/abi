"""``python -m naas_abi_apps.linkedin``: run the module until it is stopped.

Configuration from the environment: ``LINKEDIN_<FIELD>`` for each field of
``LinkedInConfiguration`` (``LINKEDIN_LI_AT_SECRET``, ``LINKEDIN_CHAT_MODEL``,
``LINKEDIN_EMBED_AT_START``, ...; see
``naas_abi_apps.common.runtime`` for the connection variables).
"""

from __future__ import annotations

import sys

from naas_abi_apps.common.runtime import main
from naas_abi_apps.linkedin import ABIModule

ENV_PREFIX = "LINKEDIN"

if __name__ == "__main__":
    sys.exit(main(ABIModule, ENV_PREFIX))
