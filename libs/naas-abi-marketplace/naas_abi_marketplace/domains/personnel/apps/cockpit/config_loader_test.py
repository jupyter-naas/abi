from naas_abi_marketplace.domains.personnel.apps.cockpit.config_loader import (
    REGISTERED_PAGE_IDS,
    load_config,
    load_default_entity,
    public_config,
)


def test_config_defines_every_registered_page_once_in_order() -> None:
    pages = load_config()["app"]["pages"]

    assert {page["page_id"] for page in pages} == REGISTERED_PAGE_IDS
    assert [page["order"] for page in pages] == sorted(
        page["order"] for page in pages
    )
    assert len({page["url"] for page in pages}) == len(pages)


def test_public_config_only_exposes_enabled_public_pages() -> None:
    config = public_config()

    assert config["app"]["pages"]
    assert all(page["enabled"] for page in config["app"]["pages"])
    assert all("public" in page["permissions"] for page in config["app"]["pages"])
    assert config["app"]["default_page"] in {
        page["page_id"] for page in config["app"]["pages"]
    }


def test_design_and_graph_parameters_are_configured() -> None:
    config = load_config()

    assert config["theme"]["css_variables"]
    assert config["theme"]["bfo_buckets"]
    assert config["graph"]["parameters"]
    assert config["graph"]["default_person_label"]


def test_default_entity_comes_from_global_entity_data() -> None:
    config = load_config()
    default_entity = load_default_entity()

    assert "default_entity" not in config["app"]
    assert public_config()["app"]["default_entity"] == default_entity
    assert default_entity["entity_type"] == "organization"
