from naas_abi.apps.nexus.apps.api.app.core.config import OrganizationSeedConfig
from naas_abi.apps.nexus.apps.api.app.core.workspace_config_seeds import workspace_seed_rows


def _orgs() -> list[OrganizationSeedConfig]:
    return [
        OrganizationSeedConfig.model_validate(
            {
                "name": "Acme",
                "slug": "acme",
                "workspaces": [
                    {"slug": "bare"},
                    {
                        "slug": "ops",
                        "primary_color": "#000000",
                        "default_agent": "Abi",
                        "agents": ["Abi", "Analyst"],
                        "apps": ["kanban"],
                        "ontologies": ["core:bfo.ttl"],
                        "graphs": {
                            "read_all": True,
                            "read": ["http://g/a"],
                            "write": ["http://g/b"],
                        },
                        "maps": {"feeds": ["flights"], "basemaps": {"custom": ["topo"]}},
                    },
                ],
            }
        )
    ]


def test_unseeded_workspace_has_no_rows() -> None:
    assert workspace_seed_rows(_orgs(), "elsewhere") == []


def test_workspace_without_preloads_has_no_rows() -> None:
    assert workspace_seed_rows(_orgs(), "bare") == []


def test_every_preload_is_listed_with_its_config_path() -> None:
    rows = workspace_seed_rows(_orgs(), "ops")

    base = "nexus_config.organizations[acme].workspaces[ops]"
    assert rows == [
        {"kind": "default_agent", "value": "Abi", "source": f"{base}.default_agent"},
        {"kind": "agent", "value": "Abi", "source": f"{base}.agents[0]"},
        {"kind": "agent", "value": "Analyst", "source": f"{base}.agents[1]"},
        {"kind": "app", "value": "kanban", "source": f"{base}.apps[0]"},
        {"kind": "ontology", "value": "core:bfo.ttl", "source": f"{base}.ontologies[0]"},
        {"kind": "graph_read_all", "value": "All graphs", "source": f"{base}.graphs.read_all"},
        {"kind": "graph_read", "value": "http://g/a", "source": f"{base}.graphs.read[0]"},
        {"kind": "graph_write", "value": "http://g/b", "source": f"{base}.graphs.write[0]"},
        {"kind": "map_feed", "value": "flights", "source": f"{base}.maps.feeds[0]"},
        {"kind": "basemap", "value": "topo", "source": f"{base}.maps.basemaps.custom[0]"},
    ]
    # Branding is config too, but not a preload.
    assert all("#000000" not in row.values() for row in rows)
