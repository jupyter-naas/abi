"""``python -m naas_abi_apps.github``: run the module until it is stopped.

Configuration: ``GITHUB_<FIELD>`` (e.g. ``GITHUB_CHAT_MODEL``,
``GITHUB_ACCESS_TOKEN_SECRET``), see ``naas_abi_apps.common.runtime``.
"""

from __future__ import annotations

import sys

from naas_abi_apps.common.runtime import main
from naas_abi_apps.github import ABIModule

ENV_PREFIX = "GITHUB"

if __name__ == "__main__":
    sys.exit(main(ABIModule, ENV_PREFIX))
