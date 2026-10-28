"""Features: ``UseFeature`` is granted by feature policies only."""

from naas_abi.apps.nexus.apps.api.app.services.iam.catalog.dsl import action, rtype

TYPES = (rtype("feature"),)
ACTIONS = (action("UseFeature", "read", "feature"),)
