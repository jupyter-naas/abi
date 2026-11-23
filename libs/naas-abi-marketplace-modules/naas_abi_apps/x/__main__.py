"""``python -m naas_abi_apps.x``: run the module until it is stopped.

Configuration: ``X_CONFIG_FILE`` (YAML or JSON: the ``config:`` of an engine
``modules:`` entry is accepted as it is), then ``X_<FIELD>`` variables, e.g.
``X_GRAPH_NAME``, ``X_CHAT_MODEL``, ``X_SEARCH_RECENT_TWEETS_WORKFLOW`` (JSON).
The bearer token is the engine secret ``applications.x/X_BEARER_TOKEN``. See
``naas_abi_apps.common.runtime`` for the connection variables.
"""

from __future__ import annotations

import sys

from naas_abi_apps.common.runtime import main
from naas_abi_apps.x import ABIModule

ENV_PREFIX = "X"

if __name__ == "__main__":
    sys.exit(main(ABIModule, ENV_PREFIX))
