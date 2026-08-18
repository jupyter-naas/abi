from naas_abi.apps.nexus.apps.api.app.utils.public_urls import resolve_public_api_host


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


def test_engine_default_defers_to_abi_port() -> None:
    assert (
        resolve_public_api_host("localhost:9879", abi_port="9967")
        == "http://localhost:9967"
    )


def test_engine_default_https_prefix_still_defers_to_abi_port() -> None:
    assert (
        resolve_public_api_host("https://localhost:9879", abi_port="9967")
        == "http://localhost:9967"
    )


def test_missing_config_uses_abi_port() -> None:
    assert (
        resolve_public_api_host(None, abi_port="9967", browser_host="127.0.0.1")
        == "http://127.0.0.1:9967"
    )


def test_loopback_without_scheme_uses_http() -> None:
    assert resolve_public_api_host("localhost:9879") == "http://localhost:9879"


def test_empty_config_and_no_port_is_none() -> None:
    assert resolve_public_api_host(None) is None
