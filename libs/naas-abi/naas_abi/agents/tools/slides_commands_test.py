from naas_abi.agents.tools.slides_commands import (
    apply_slide_commands,
    last_rename_deck_title,
    update_deck_title,
)

_SAMPLE = """<!doctype html><html><head><title>Presentation Title</title></head>
<body><main class="deck">
<section id="slide-cover" class="slide cover">
<h1>Presentation Title</h1>
<p class="subtitle">Overview</p>
</section>
<section id="slide-agenda" class="slide">
<h1>Agenda</h1>
<p>Session details</p>
</section>
</main></body></html>"""


def test_update_deck_title_sets_tab_and_cover() -> None:
    updated = update_deck_title(_SAMPLE, "Forvis Mazars Story")
    assert isinstance(updated, str)
    assert "<title>Forvis Mazars Story</title>" in updated
    assert "<h1>Forvis Mazars Story</h1>" in updated
    assert "<h1>Agenda</h1>" in updated


def test_rename_deck_command_updates_html_title() -> None:
    result = apply_slide_commands(
        _SAMPLE,
        [{"type": "rename_deck", "title": "Forvis Mazars Story"}],
    )
    assert result["ok"] is True
    assert "<h1>Forvis Mazars Story</h1>" in result["html"]
    assert result["applied"] == ["rename_deck"]


def test_update_title_command_is_heading_only_html() -> None:
    result = apply_slide_commands(
        _SAMPLE,
        [{"type": "update_title", "title": "Cover only"}],
    )
    assert result["ok"] is True
    assert "<h1>Cover only</h1>" in result["html"]
    assert last_rename_deck_title([{"type": "update_title", "title": "Cover only"}]) == ""


def test_last_rename_deck_title_reads_the_batch() -> None:
    assert (
        last_rename_deck_title(
            [
                {"type": "update_title", "title": "Heading only"},
                {"type": "rename_deck", "title": "Forvis Mazars Story"},
            ]
        )
        == "Forvis Mazars Story"
    )
    assert last_rename_deck_title([{"type": "update_title", "title": "X"}]) == ""


def test_unknown_command_is_rejected() -> None:
    result = apply_slide_commands(_SAMPLE, [{"type": "insert_slide"}])
    assert "error" in result
    assert "rename_deck" in result["error"]


def test_empty_requests_rejected() -> None:
    assert "error" in apply_slide_commands(_SAMPLE, [])
