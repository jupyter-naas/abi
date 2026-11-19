"""Analytics and system administration.

Analytics are read in a scope (epic #1533): an organization's
(``ReadOrganizationAnalytics``, decided on the organization, its owners' and
admins') or a workspace's (``ReadWorkspaceAnalytics``, decided on the workspace,
its admins' and owners', the organization's owners and admins through their
org-wide role). The messages of a conversation behind the figures are
``ReadAnalyticsConversation`` on ``analytics_conversation/<conversation>`` in the
conversation's workspace: a policy grants it, no role holds it. The tracker's
ingest is any signed-in user's (``POST /api/analytics/events``).

``ReadAnalytics`` and ``WriteAnalytics`` on the platform singleton serve the
platform-wide analytics app until its removal (#1536).
"""

from naas_abi.apps.nexus.apps.api.app.services.iam.catalog.dsl import action, rtype

TYPES = (
    rtype("analytics", id="singleton", platform=True),
    rtype(
        "analytics_conversation",
        policy_only=True,
        description="A conversation's messages as the analytics show them",
    ),
    rtype("system", id="singleton", platform=True),
)

ACTIONS = (
    action("ReadAnalytics", "read", "analytics"),
    action("WriteAnalytics", "admin", "analytics"),
    action(
        "ReadOrganizationAnalytics",
        "admin",
        "organization",
        description="Read the usage analytics of the organization's members and workspaces",
    ),
    action(
        "ReadWorkspaceAnalytics",
        "admin",
        "workspace",
        description="Read the usage analytics of the workspace's members",
    ),
    action(
        "ReadAnalyticsConversation",
        "read",
        "analytics_conversation",
        description="Read and export a conversation's messages from the analytics",
    ),
    # Overview, services, modules, telemetry, NATS, traffic, traces, jobs, runs.
    action("ReadSystem", "read", "system"),
    # Reveal, edit or delete entries, trigger or cancel jobs and runs, Ollama pull.
    action("ManageSystem", "admin", "system"),
)
