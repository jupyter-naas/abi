"""Features: ``UseFeature`` is granted by policies only, never by a role."""

from naas_abi.apps.nexus.apps.api.app.services.iam.catalog.dsl import action, rtype

TYPES = (rtype("feature", policy_only=True),)
ACTIONS = (action("UseFeature", "read", "feature"),)
