from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.core.frame_headers import embed_csp, is_embeddable


def test_only_app_html_and_previews_are_embeddable() -> None:
    assert is_embeddable("/app-html/bob/budget/index.html")
    assert is_embeddable("/app-preview/tok/index.html")
    assert not is_embeddable("/api/app-projects/")
    assert not is_embeddable("/app-previewer/x")


def test_embed_csp_keeps_the_route_sandbox() -> None:
    ancestors = ["'self'", "https://nexus.example.com"]
    assert embed_csp(None, ancestors) == "frame-ancestors 'self' https://nexus.example.com;"
    assert embed_csp("sandbox allow-scripts;", ancestors) == (
        "sandbox allow-scripts; frame-ancestors 'self' https://nexus.example.com;"
    )
