"""Graph views, ontology and maps (search and its topics are in ``search``).

The knowledge graph's own data is ``triple_store`` data: the graph routes ask the
kernel (``triple_store:Query``, ``Insert``, ...) as the signed-in user, and the
kernel decides by where IAM placed each graph. Only what Nexus keeps itself is
declared here.
"""

from naas_abi.apps.nexus.apps.api.app.services.iam.catalog.dsl import action, rtype

TYPES = (
    rtype("view"),
    rtype("graph_cache", id="singleton"),
    rtype("ontology"),
    rtype("icon"),
    rtype("layout"),
    rtype("layer"),
    # The Maps catalog (``services/maps/AGENTS.md``): a feed is a
    # ``layout``; its layers, the basemaps, what the catalog read returns and who
    # may share what across workspaces are named here.
    rtype("feed_layer"),
    rtype("basemap"),
    rtype("maps_catalog", id="singleton"),
    rtype("maps_access", id="singleton"),
)

ACTIONS = (
    action("ListViews", "list", "view", feature="graph"),
    action("GetView", "read", "view", feature="graph"),
    action("CreateView", "write", "view", feature="graph"),
    action("UpdateView", "write", "view", feature="graph"),
    action("DeleteView", "write", "view", feature="graph"),
    # Clearing the workspace's graph caches only costs everybody a recompute.
    action("RefreshGraphCache", "write", "graph_cache", feature="graph"),
    action("ListOntologies", "list", "ontology", feature="ontology"),
    action("GetOntology", "read", "ontology", feature="ontology"),
    action("ExportOntology", "read", "ontology", feature="ontology"),
    action("ImportOntology", "write", "ontology", feature="ontology"),
    action("CreateOntologyEntity", "write", "ontology", feature="ontology"),
    action("DeleteOntologyEntity", "write", "ontology", feature="ontology"),
    action("ListIcons", "list", "icon", feature="ontology"),
    action("UpdateIcons", "write", "icon", feature="ontology"),
    action("RefreshOntologyCache", "admin", "ontology", feature="ontology"),
    # A layout is a query the whole workspace's map runs: only admins author,
    # hide or preview one (they always have), everybody reads.
    action("ListLayouts", "list", "layout", feature="maps"),
    action("GetLayout", "read", "layout", feature="maps"),
    action("UpdateLayout", "admin", "layout", feature="maps"),
    action("DeleteLayout", "admin", "layout", feature="maps"),
    action("SetLayoutVisibility", "admin", "layout", feature="maps"),
    action("PreviewLayout", "admin", "layout", feature="maps"),
    action("ListLayers", "list", "layer", feature="maps"),
    action("GetLayer", "read", "layer", feature="maps"),
    # A feed's layers (views on one feed) follow the feed: everybody reads, admins author.
    action("ListFeedLayers", "list", "feed_layer", feature="maps"),
    action("GetFeedLayer", "read", "feed_layer", feature="maps"),
    action("UpdateFeedLayer", "admin", "feed_layer", feature="maps"),
    action("DeleteFeedLayer", "admin", "feed_layer", feature="maps"),
    action("ListBasemaps", "list", "basemap", feature="maps"),
    action("GetBasemap", "read", "basemap", feature="maps"),
    action("UpdateBasemap", "admin", "basemap", feature="maps"),
    action("DeleteBasemap", "admin", "basemap", feature="maps"),
    action("SetBasemapVisibility", "admin", "basemap", feature="maps"),
    action("GetMapsCatalog", "read", "maps_catalog", feature="maps"),
    # Which workspaces may use each deployment item and each custom one: the
    # administrators' (changing a deployment item or sharing with every workspace
    # is further narrowed to a platform administrator by ``permissions/service``).
    action("GetMapsAccess", "admin", "maps_access", feature="maps"),
    action("UpdateMapsAccess", "admin", "maps_access", feature="maps"),
)
