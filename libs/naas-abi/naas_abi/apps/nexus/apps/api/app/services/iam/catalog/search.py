"""Search and its topics: ``topic/<id>``, ``search_scope/<id>``, ``search/-``, and the
sources a search reads (``search_source/<id>``: a feature searched, ``web.<engine>``).

A source is used where the workspace's offer names it ("<W> access", section
``OfferSearchSources``): no role holds one, the level policies grant the type and the
offer bounds it (``workspace_offer``)."""

from naas_abi.apps.nexus.apps.api.app.services.iam.catalog.dsl import action, rtype

TYPES = (
    rtype("search", id="singleton"),
    rtype("topic"),
    rtype("search_scope"),
    rtype("search_source", policy_only=True),
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
    # Deprecated: the sources are the workspace's offer (``UseSearchSource``); it
    # authorizes nothing (IAM refuses a catalog dropping an action a policy names).
    action("SetSearchScope", "admin", "search_scope", feature="search"),
    # Read a source of the search: a feature's items, or a web engine (the query
    # leaves Nexus). Where the workspace's offer names it.
    action("UseSearchSource", "read", "search_source", feature="search"),
)
