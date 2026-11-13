"""The office converter runs as a child kept apart from the API process."""

from __future__ import annotations

import http.server
import json
import shutil
import stat
import sys
import threading
from pathlib import Path

import pytest
from naas_abi.apps.nexus.apps.api.app.services.files import office_conversion
from naas_abi.apps.nexus.apps.api.app.services.files.office_conversion import (
    ConversionFailed,
    convert_to_pdf,
)

STAND_IN = """#!{python}
import json, os, resource, sys, time
from pathlib import Path
args = sys.argv[1:]
time.sleep(0.2)  # the limits are in place by now on either path
Path({record!r}).write_text(json.dumps({{
    "argv": args,
    "env": dict(os.environ),
    "sid": os.getsid(0) == os.getpid(),
    "limits": [resource.getrlimit(k)[0] for k in (
        resource.RLIMIT_AS, resource.RLIMIT_CPU, resource.RLIMIT_FSIZE, resource.RLIMIT_NOFILE
    )],
}}))
if {sleep}:
    time.sleep({sleep})
out = Path(args[args.index("--outdir") + 1])
(out / (Path(args[-1]).stem + ".pdf")).write_bytes(b"%PDF-1.4 stand-in")
"""


def _stand_in(tmp_path: Path, sleep: float = 0) -> tuple[str, Path]:
    record = tmp_path / "record.json"
    script = tmp_path / "soffice"
    script.write_text(STAND_IN.format(python=sys.executable, record=str(record), sleep=sleep))
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script), record


def test_office_conversion_keeps_the_api_environment_out(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ABI_API_KEY", "a-secret-of-the-api")
    monkeypatch.setenv("OPENAI_API_KEY", "another-secret")
    soffice, record = _stand_in(tmp_path)

    pdf = convert_to_pdf(soffice, "deck.docx", b"PK user bytes")

    assert pdf.startswith(b"%PDF")
    seen = json.loads(record.read_text())
    assert "a-secret-of-the-api" not in json.dumps(seen["env"])
    assert "another-secret" not in json.dumps(seen["env"])
    assert set(seen["env"]) <= {
        "PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "SAL_USE_VCLPLUGIN", "PWD", "LC_CTYPE",
    }
    assert seen["sid"] is True  # a session of its own, killed as a whole
    profile = [a for a in seen["argv"] if a.startswith("-env:UserInstallation=")]
    assert len(profile) == 1
    settings = Path(profile[0].split("=", 1)[1].removeprefix("file://")) / "user"
    assert seen["env"]["HOME"] in profile[0]  # the job's own folder, not a shared one
    assert not settings.exists()  # the job's folder is gone once it ends


@pytest.mark.parametrize("with_prlimit", [True, False])
def test_office_conversion_keeps_its_resource_limits(tmp_path, monkeypatch, with_prlimit) -> None:
    if with_prlimit and not shutil.which("prlimit"):
        pytest.skip("prlimit is not installed")
    if not with_prlimit:
        real_which = shutil.which
        monkeypatch.setattr(
            office_conversion.shutil,
            "which",
            lambda name, *a, **k: None if name == "prlimit" else real_which(name, *a, **k),
        )
    soffice, record = _stand_in(tmp_path)
    convert_to_pdf(soffice, "deck.docx", b"PK")
    seen = json.loads(record.read_text())
    assert seen["limits"] == [value for _, value in office_conversion._LIMITS]
    assert seen["sid"] is True


def test_office_conversion_keeps_its_deadline(tmp_path) -> None:
    soffice, _ = _stand_in(tmp_path, sleep=30)
    with pytest.raises(ConversionFailed, match="timed out"):
        convert_to_pdf(soffice, "deck.docx", b"PK", timeout=1)


def test_office_conversion_keeps_links_and_macros_off_in_its_profile() -> None:
    settings = office_conversion.PROFILE_SETTINGS
    assert '"DisableMacrosExecution"' in settings and "<value>true</value>" in settings
    assert '"BlockUntrustedRefererLinks"' in settings
    assert settings.count('oor:name="Link" oor:op="fuse"><value>2</value>') == 2


@pytest.mark.skipif(not shutil.which("soffice"), reason="LibreOffice is not installed")
def test_office_preview_keeps_linked_content_unloaded() -> None:
    """A document that links an image by URL renders without fetching it."""
    hits: list[str] = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            hits.append(self.path)
            self.send_response(404)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/linked.png"
        document = f"""<?xml version="1.0" encoding="UTF-8"?>
<office:document xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"
 xmlns:xlink="http://www.w3.org/1999/xlink"
 xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0"
 office:version="1.3" office:mimetype="application/vnd.oasis.opendocument.text">
<office:body><office:text><text:p>Linked:<draw:frame svg:width="2cm" svg:height="2cm">
<draw:image xlink:href="{url}" xlink:type="simple" xlink:show="embed" xlink:actuate="onLoad"/>
</draw:frame></text:p></office:text></office:body></office:document>""".encode()
        pdf = convert_to_pdf(shutil.which("soffice") or "soffice", "linked.fodt", document)
    finally:
        server.shutdown()
    assert pdf.startswith(b"%PDF")
    assert hits == []
