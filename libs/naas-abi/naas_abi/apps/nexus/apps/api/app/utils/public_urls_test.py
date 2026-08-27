from naas_abi.apps.nexus.apps.api.app.utils.public_urls import (
    resolve_module_public_asset_path,
    resolve_public_api_host,
)


def test_resolve_module_public_asset_path_rewrites_legacy_flat_module_name() -> None:
    assert (
        resolve_module_public_asset_path(
            "report/assets/public/avatar.png",
            abi_module_path="operations.report",
        )
        == "operations/report/assets/public/avatar.png"
    )


def test_resolve_module_public_asset_path_rewrites_modules_prefix() -> None:
    assert (
        resolve_module_public_asset_path(
            "/modules/report/assets/public/avatar.png",
            abi_module_path="operations.report",
        )
        == "operations/report/assets/public/avatar.png"
    )


def test_resolve_module_public_asset_path_keeps_full_nested_path() -> None:
    assert (
        resolve_module_public_asset_path(
            "operations/report/assets/public/avatar.png",
            abi_module_path="operations.report",
        )
        == "operations/report/assets/public/avatar.png"
    )


def test_resolve_module_public_asset_path_keeps_marketplace_full_path() -> None:
    path = (
        "naas_abi_marketplace/domains/operations/assets/public/"
        "project-manager.png"
    )
    assert (
        resolve_module_public_asset_path(
            path,
            abi_module_path="naas_abi_marketplace.domains.operations",
        )
        == path
    )


def test_explicit_public_hostname_is_kept() -> None:
    assert (
        resolve_public_api_host("https://api.example.com", abi_port="9967")
        == "https://api.example.com"
    )


def test_explicit_hostname_without_scheme_gets_https() -> None:
    assert (
        resolve_public_api_host("api.example.com", abi_port="9967")
        == "https://api.example.com"
    )


def test_docker_local_hostname_is_not_loopback() -> None:
    assert (
        resolve_public_api_host("api.localhost", abi_port="9967")
        == "https://api.localhost"
    )


def test_loopback_any_port_defers_to_abi_port() -> None:
    assert (
        resolve_public_api_host("localhost:9879", abi_port="9967")
        == "http://localhost:9967"
    )
    assert (
        resolve_public_api_host("http://127.0.0.1:10400", abi_port="9967")
        == "http://localhost:9967"
    )


def test_loopback_https_prefix_still_defers_to_abi_port() -> None:
    assert (
        resolve_public_api_host("https://localhost:9879", abi_port="9967")
        == "http://localhost:9967"
    )


def test_missing_config_uses_abi_port() -> None:
    assert (
        resolve_public_api_host(None, abi_port="9967", browser_host="127.0.0.1")
        == "http://127.0.0.1:9967"
    )


def test_dev_origin_wins_over_public_hostname() -> None:
    assert (
        resolve_public_api_host(
            "https://api.example.com",
            abi_port="10400",
            dev_origin="http://localhost:9967",
        )
        == "http://localhost:9967"
    )


def test_loopback_without_scheme_uses_http() -> None:
    assert resolve_public_api_host("localhost:9879") == "http://localhost:9879"


def test_empty_config_and_no_port_is_none() -> None:
    assert resolve_public_api_host(None) is None
