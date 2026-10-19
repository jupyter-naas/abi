"""Search and its topics: ``topic/<id>``, ``search_scope/<id>``, ``search/-``."""

from naas_abi.apps.nexus.apps.api.app.services.iam.catalog.dsl import action, rtype

TYPES = (
    rtype("search", id="singleton"),
    rtype("topic"),
    rtype("search_scope"),
)

ACTIONS = (
    # A search of the workspace's private sources.
    action("Search", "read", "search", feature="search"),
    action("ListTopics", "list", "topic", feature="search"),
    # A topic's results and the detail of one of them.
    action("GetTopic", "read", "topic", feature="search"),
    # Topic definitions are the workspace's to administer: edit, reset, delete,
    # and preview a raw query template.
    action("UpdateTopic", "admin", "topic", feature="search"),
    action("DeleteTopic", "admin", "topic", feature="search"),
    action("PreviewTopic", "admin", "topic", feature="search"),
    # Retire the workspace's cached responses.
    action("RefreshTopics", "write", "topic", feature="search"),
    # Switch a Nexus feature or a web engine on or off in the workspace's search.
    action("SetSearchScope", "admin", "search_scope", feature="search"),
)
