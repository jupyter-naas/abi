"""The platform's drives (Platform Settings > Drives, ``services/drives``).

A drive is where files are stored: the File System (the engine's object storage)
today, others later. It is a platform resource, ``abi:nexus:drive/<id>`` (``-`` for
the list). No role reaches it: the platform admin holds it, or whoever a policy
grants it to.
"""

from naas_abi.apps.nexus.apps.api.app.services.iam.catalog.dsl import action, rtype

TYPES = (rtype("drive", platform=True, description="A storage backend of the platform."),)

ACTIONS = (
    action(
        "ListDrives",
        "list",
        "drive",
        description=(
            "List the platform's drives: type, provider, location and whether each answers; "
            "never a credential."
        ),
    ),
)
