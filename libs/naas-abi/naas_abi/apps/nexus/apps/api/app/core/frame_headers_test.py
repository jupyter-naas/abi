from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.core.frame_headers import (
    embed_csp,
    frame_ancestors,
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
