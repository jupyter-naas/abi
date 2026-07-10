"""Unit tests for workspace slide templates."""

from __future__ import annotations

from pathlib import Path

from desktop.core.templates import (
    DATA_GOVERNANCE_SLIDE,
    ensure_templates,
    sanitize_template_filename,
)


def test_sanitize_template_filename() -> None:
    assert (
        sanitize_template_filename("Data_Governance_Quality_ISO27001 2 (2).html")
        == "data-governance-quality-iso27001-2.html"
    )
    assert sanitize_template_filename("My Slide.HTML") == "my-slide.html"


def test_ensure_templates_creates_slides_dir(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    slides = ensure_templates(workspace)

    assert slides.is_dir()
    assert (slides / "README.md").is_file()
    assert (slides / "starter-deck.html").is_file()
    assert "slide" in (slides / "starter-deck.html").read_text(encoding="utf-8")


def test_ensure_templates_copies_source_slide_when_present(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    source = tmp_path / "external.html"
    source.write_text("<html><body>ISO deck</body></html>", encoding="utf-8")

    ensure_templates(workspace, source_slide=source)

    copied = workspace / "templates" / "slides" / DATA_GOVERNANCE_SLIDE
    assert copied.read_text(encoding="utf-8") == "<html><body>ISO deck</body></html>"


def test_ensure_templates_does_not_overwrite_existing_copy(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    slides = workspace / "templates" / "slides"
    slides.mkdir(parents=True)
    target = slides / DATA_GOVERNANCE_SLIDE
    target.write_text("keep me", encoding="utf-8")
    source = tmp_path / "new.html"
    source.write_text("replace me", encoding="utf-8")

    ensure_templates(workspace, source_slide=source)

    assert target.read_text(encoding="utf-8") == "keep me"
