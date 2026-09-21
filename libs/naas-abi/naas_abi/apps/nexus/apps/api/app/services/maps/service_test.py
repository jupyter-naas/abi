from unittest.mock import Mock

import pytest
from naas_abi.apps.nexus.apps.api.app.services.graph.access import GraphAccessScope
from naas_abi.apps.nexus.apps.api.app.services.graph.graph__schema import GraphAccessError
from naas_abi.apps.nexus.apps.api.app.services.maps.service import GraphMapLayer, MapsCatalog


def test_catalog_and_feed_enforce_graph_grants_before_query():
    catalog = MapsCatalog()
    feed = Mock(return_value={"pins": []})
    catalog.register(
        GraphMapLayer(
            "example-offices", "Example offices", "Published locations", "urn:allowed", feed
        )
    )
    denied = GraphAccessScope("other", frozenset({"urn:other"}), frozenset())
    assert catalog.list_layers(denied) == []
    with pytest.raises(GraphAccessError):
        catalog.feed("example-offices", denied, Mock())
    feed.assert_not_called()
    scope = GraphAccessScope("workspace", frozenset({"urn:allowed"}), frozenset())
    assert catalog.list_layers(scope)[0]["id"] == "example-offices"
    store = Mock()
    assert catalog.feed("example-offices", scope, store)["pins"] == []
    feed.assert_called_once_with(store)
