from __future__ import annotations

from urllib.parse import unquote

import pytest
from naas_abi.apps.nexus.apps.api.app.core.content_disposition import content_disposition
from starlette.responses import Response


def test_ascii_filename_keeps_the_plain_header() -> None:
    assert content_disposition("inline", "report.pdf") == 'inline; filename="report.pdf"'
    assert content_disposition("attachment", "data.zip") == 'attachment; filename="data.zip"'


def test_decomposed_accents_get_an_ascii_fallback_and_utf8_name() -> None:
    # macOS stores "é" as "e" + U+0301; that combining mark is not latin-1.
    name = "Accusé de réception-1.pdf"

    header = content_disposition("inline", name)

    assert header.startswith('inline; filename="Accuse de reception-1.pdf"; ')
    encoded = header.split("filename*=UTF-8''", 1)[1]
    assert unquote(encoded) == name


def test_non_latin_script_falls_back_to_download_with_extension() -> None:
    header = content_disposition("attachment", "報告.pdf")

    assert header.startswith('attachment; filename="download.pdf"; ')
    assert unquote(header.split("filename*=UTF-8''", 1)[1]) == "報告.pdf"


@pytest.mark.parametrize("name", ['say "hi".txt', "a\\b.txt", "evil\r\nSet-Cookie: x.txt"])
def test_quotes_backslashes_and_line_breaks_cannot_escape_the_header(name: str) -> None:
    header = content_disposition("attachment", name)

    fallback = header.split('filename="', 1)[1].split('"', 1)[0]
    assert '"' not in fallback and "\\" not in fallback
    assert "\r" not in header and "\n" not in header
    assert unquote(header.split("filename*=UTF-8''", 1)[1]) == name


@pytest.mark.parametrize(
    "name", ["Accusé.pdf", "Résumé.docx", "報告.pdf", "emoji 🚀.png", "plain.txt"]
)
def test_header_is_accepted_by_starlette(name: str) -> None:
    # Starlette encodes header values as latin-1; this used to raise.
    response = Response(content=b"x", headers={"Content-Disposition": content_disposition("inline", name)})

    assert response.headers["content-disposition"].startswith("inline; filename=")
