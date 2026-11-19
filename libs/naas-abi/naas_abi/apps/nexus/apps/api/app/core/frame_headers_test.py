from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.core.frame_headers import (
    embed_csp,
    frame_ancestors,
    frame_origin,
    ignored_frame_origins,
    is_embeddable,
)


def test_only_app_html_previews_and_remote_apps_are_embeddable() -> None:
    assert is_embeddable("/app-html/bob/budget/index.html")
    assert is_embeddable("/app-preview/tok/index.html")
    assert is_embeddable("/app-remote/grant/acme.research/console/index.html")
    assert not is_embeddable("/api/app-projects/")
    assert not is_embeddable("/app-previewer/x")


def test_embed_csp_keeps_the_route_sandbox() -> None:
    ancestors = ["'self'", "https://nexus.example.com"]
    assert embed_csp(None, ancestors) == "frame-ancestors 'self' https://nexus.example.com;"
    assert embed_csp("sandbox allow-scripts;", ancestors) == (
        "sandbox allow-scripts; frame-ancestors 'self' https://nexus.example.com;"
    )


def test_frame_ancestors_come_from_configuration_only() -> None:
    assert frame_ancestors(
        "https://nexus.example.com/",
        ["https://nexus.example.com", "http://localhost:3042/", ""],
    ) == ["'self'", "https://nexus.example.com", "http://localhost:3042"]
    assert frame_ancestors("", ()) == ["'self'"]
    assert frame_ancestors(None, ["https://admin.example"]) == ["'self'", "https://admin.example"]


@pytest.mark.parametrize(
    ("entry", "origin"),
    [
        ("https://nexus.example", "https://nexus.example"),
        ("http://localhost:3042", "http://localhost:3042"),
        ("http://127.0.0.1:9879", "http://127.0.0.1:9879"),
        ("HTTPS://Nexus.Example", "https://nexus.example"),
        (" https://admin.example/ ", "https://admin.example"),
    ],
)
def test_a_real_origin_is_kept(entry: str, origin: str) -> None:
    assert frame_origin(entry) == origin


@pytest.mark.parametrize(
    "entry",
    [
        "*",
        "https://*.example.com",
        "http://",
        "https://",
        "",
        "'self'",
        "'none'",
        "https://a.example; script-src *",
        "https://a.example b.example",
        "https://a.example,https://b.example",
        "https://a.example/path",
        "https://a.example?x=1",
        "https://a.example#x",
        "https://user@a.example",
        "https://a.example:port",
        "https://[::1]:3000",
        "ftp://a.example",
        "javascript:alert(1)",
        "data:",
        "https://a.example\nscript-src *",
        "https://a.example//",
        "https://.example",
        "https://a..example",
    ],
)
def test_anything_else_is_not_an_origin(entry: str) -> None:
    assert frame_origin(entry) is None


def test_a_wildcard_alone_leaves_only_self() -> None:
    assert frame_ancestors(None, ["*"]) == ["'self'"]


def test_ancestors_keep_valid_origins_in_order_once_each() -> None:
    cors = [
        "https://nexus.example/",
        "*",
        "http://localhost:3042",
        "https://x.example; script-src *",
        "HTTPS://NEXUS.EXAMPLE",
        "http://",
    ]
    assert frame_ancestors("https://nexus.example", cors) == [
        "'self'",
        "https://nexus.example",
        "http://localhost:3042",
    ]


def test_a_malformed_frontend_url_is_dropped() -> None:
    assert frame_ancestors("https://nexus.example/app", ["https://admin.example"]) == [
        "'self'",
        "https://admin.example",
    ]


def test_the_dropped_entries_are_named() -> None:
    cors = ["https://admin.example", "*", "", "  ", "https://x.example; script-src *", "http://"]
    assert ignored_frame_origins("https://nexus.example/app", cors) == [
        "https://nexus.example/app",
        "*",
        "https://x.example; script-src *",
        "http://",
    ]
    assert ignored_frame_origins(None, ["https://admin.example"]) == []
