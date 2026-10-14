"""The slides CLI edits a deck.html file through slides_tools helpers."""

from __future__ import annotations

from naas_abi.tools.slides_cli import main

_DECK = """<!DOCTYPE html><html><body><main>
<section class="slide"><h1>Cover Title</h1><p>Keep</p></section>
<section class="slide"><h1>Cover Title</h1></section>
</main></body></html>
"""


def test_replace_command_edits_one_node(tmp_path):
    src = tmp_path / "deck.html"
    out = tmp_path / "out.html"
    src.write_text(_DECK, encoding="utf-8")
    code = main(
        [
            "replace",
            str(src),
            "--old",
            "Cover Title",
            "--new",
            "Q3",
            "--element-path",
            "0:h1:0",
            "-o",
            str(out),
        ]
    )
    assert code == 0
    written = out.read_text(encoding="utf-8")
    assert "<h1>Q3</h1>" in written
    assert "<h1>Cover Title</h1>" in written
    assert "<p>Keep</p>" in written
    assert src.read_text(encoding="utf-8") == _DECK
