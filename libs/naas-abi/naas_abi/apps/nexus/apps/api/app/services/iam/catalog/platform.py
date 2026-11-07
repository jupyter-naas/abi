"""Analytics and system administration."""

from naas_abi.apps.nexus.apps.api.app.services.iam.catalog.dsl import action, rtype

TYPES = (
    rtype("analytics", id="singleton", platform=True),
    rtype("system", id="singleton", platform=True),
)

ACTIONS = (
    action("ReadAnalytics", "read", "analytics"),
    action("WriteAnalytics", "admin", "analytics"),
    # Overview, services, modules, telemetry, NATS, traffic, traces, jobs, runs.
    action("ReadSystem", "read", "system"),
    # Reveal, edit or delete entries, trigger or cancel jobs and runs, Ollama pull.
    action("ManageSystem", "admin", "system"),
)
