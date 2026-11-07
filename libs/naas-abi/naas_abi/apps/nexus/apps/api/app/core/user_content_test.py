from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.core.user_content import (
    harden_active_content,
    is_active_media_type,
    user_content_headers,
    with_sandbox,
)


@pytest.mark.parametrize(
    "media_type",
    [
        "image/svg+xml",
        "text/html; charset=utf-8",
        "TEXT/HTML",
        "application/xhtml+xml",
        "text/xml",
        "application/xml",
        "application/atom+xml",
        "text/javascript",
        "application/javascript",
    ],
)
def test_markup_svg_and_script_are_active(media_type: str) -> None:
    assert is_active_media_type(media_type)


@pytest.mark.parametrize(
    "media_type",
    ["image/png", "application/pdf", "application/json", "text/plain", "text/markdown", None, ""],
)
def test_images_documents_and_data_are_not(media_type: str | None) -> None:
    assert not is_active_media_type(media_type)


def test_a_route_serving_user_files_sandboxes_all_of_them_and_downloads_the_active_ones() -> None:
    svg = user_content_headers("x.svg", "image/svg+xml")
    assert svg["Content-Disposition"].startswith("attachment")
    assert svg["Content-Security-Policy"] == "sandbox"
    assert svg["X-Content-Type-Options"] == "nosniff"

    png = user_content_headers("x.png", "image/png")
    assert png["Content-Disposition"].startswith("inline")
    assert png["Content-Security-Policy"] == "sandbox"


def test_the_sandbox_directive_is_added_once_and_keeps_the_other_directives() -> None:
    assert with_sandbox(None) == "sandbox"
    assert with_sandbox("default-src 'self';") == "sandbox; default-src 'self'"
    assert with_sandbox("sandbox allow-forms") == "sandbox allow-forms"
    assert with_sandbox("default-src 'self'; sandbox") == "default-src 'self'; sandbox"


def test_an_active_response_is_sandboxed_and_becomes_a_download() -> None:
    headers = {"content-type": "text/html", "content-disposition": 'inline; filename="a.html"'}
    harden_active_content(headers)
    assert headers["Content-Security-Policy"] == "sandbox"
    assert headers["Content-Disposition"] == 'attachment; filename="a.html"'

    bare = {"content-type": "image/svg+xml"}
    harden_active_content(bare)
    assert bare["Content-Disposition"] == "attachment"


def test_other_responses_are_left_alone() -> None:
    headers = {"content-type": "application/json"}
    harden_active_content(headers)
    assert headers == {"content-type": "application/json"}
