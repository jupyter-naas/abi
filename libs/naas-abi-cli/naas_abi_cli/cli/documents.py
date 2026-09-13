"""Nexus Documents CLI. Same verbs as HTTP /api/documents and DocumentsAgent."""

from __future__ import annotations

import json
from pathlib import Path

import click

from naas_abi.agents.tools.documents_commands import (
    apply_document_commands,
    delete_block,
    heading_outline,
    insert_heading,
    insert_list,
    insert_page_break,
    insert_paragraph,
    insert_table,
    reflow_document,
    replace_text,
    update_document_title,
    update_paragraph_style,
)
from naas_abi.agents.tools.documents_slots import fill_document_slots

DOCUMENTS_VERBS = (
    "new",
    "open",
    "list",
    "rename",
    "style",
    "insert-heading",
    "insert-paragraph",
    "insert-page-break",
    "insert-list",
    "insert-table",
    "replace-text",
    "delete",
    "fill",
    "reflow",
    "apply",
)


def _read_html(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _write_html(path: str, html: str) -> None:
    Path(path).write_text(html, encoding="utf-8")


def _emit(result: object) -> None:
    if isinstance(result, dict):
        click.echo(json.dumps(result, ensure_ascii=False))
        if result.get("error"):
            raise SystemExit(1)
        return
    click.echo(str(result))


@click.group("documents")
def documents() -> None:
    """Edit document.html with the same mutators as HTTP and DocumentsAgent."""


@documents.command("new")
@click.option("--html", "html_path", type=click.Path(), required=True)
@click.option("--title", default="Untitled document")
def documents_new(html_path: str, title: str) -> None:
    """Create a local document.html seed (HTTP POST /projects twin)."""
    html = (
        "<!doctype html><html><head>"
        f"<title>{title}</title></head><body><main class=\"document\">"
        f"<section class=\"page flow\"><div class=\"doc-body\">"
        f"<h1 class=\"fmz-title\" data-slot=\"title\">{title}</h1>"
        "</div></section></main></body></html>"
    )
    _write_html(html_path, html)
    _emit({"ok": True, "html": html_path, "title": title})


@documents.command("open")
@click.option("--html", "html_path", type=click.Path(exists=True), required=True)
def documents_open(html_path: str) -> None:
    """Print the heading outline (HTTP GET document twin)."""
    outline = heading_outline(_read_html(html_path))
    _emit({"ok": True, "outline": outline})


@documents.command("list")
@click.option("--dir", "root", type=click.Path(exists=True), default=".")
def documents_list(root: str) -> None:
    """List document.html files under a folder (HTTP GET /projects twin)."""
    found = sorted(str(path) for path in Path(root).rglob("document.html"))
    _emit({"ok": True, "documents": found})


@documents.command("rename")
@click.option("--html", "html_path", type=click.Path(exists=True), required=True)
@click.option("--title", required=True)
def documents_rename(html_path: str, title: str) -> None:
    """Rename cover H1 and tab title. Sidebar project.json is the HTTP/agent path."""
    result = update_document_title(_read_html(html_path), title)
    if isinstance(result, dict):
        _emit(result)
        return
    _write_html(html_path, result)
    _emit({"ok": True, "title": title})


@documents.command("style")
@click.option("--html", "html_path", type=click.Path(exists=True), required=True)
@click.option("--style", "style_name", required=True)
@click.option("--slot", default="")
@click.option("--class-name", default="")
@click.option("--heading-index", type=int, default=None)
def documents_style(
    html_path: str,
    style_name: str,
    slot: str,
    class_name: str,
    heading_index: int | None,
) -> None:
    result = update_paragraph_style(
        _read_html(html_path),
        heading_index,
        style_name,
        slot=slot or None,
        class_name=class_name or None,
    )
    if isinstance(result, dict):
        _emit(result)
        return
    _write_html(html_path, result)
    _emit({"ok": True, "style": style_name})


@documents.command("insert-heading")
@click.option("--html", "html_path", type=click.Path(exists=True), required=True)
@click.option("--title", default="Heading")
@click.option("--level", type=int, default=2)
@click.option("--after-heading", type=int, default=-1)
def documents_insert_heading(
    html_path: str, title: str, level: int, after_heading: int
) -> None:
    html = insert_heading(_read_html(html_path), title, level, after_heading)
    _write_html(html_path, html)
    _emit({"ok": True})


@documents.command("insert-paragraph")
@click.option("--html", "html_path", type=click.Path(exists=True), required=True)
@click.option("--text", default="")
@click.option("--after-heading", type=int, default=-1)
def documents_insert_paragraph(html_path: str, text: str, after_heading: int) -> None:
    html = insert_paragraph(_read_html(html_path), text, after_heading)
    _write_html(html_path, html)
    _emit({"ok": True})


@documents.command("insert-page-break")
@click.option("--html", "html_path", type=click.Path(exists=True), required=True)
@click.option("--after-heading", type=int, default=-1)
def documents_insert_page_break(html_path: str, after_heading: int) -> None:
    html = insert_page_break(_read_html(html_path), after_heading)
    _write_html(html_path, html)
    _emit({"ok": True})


@documents.command("insert-list")
@click.option("--html", "html_path", type=click.Path(exists=True), required=True)
@click.option("--item", "items", multiple=True)
@click.option("--after-heading", type=int, default=-1)
@click.option("--ordered", is_flag=True)
def documents_insert_list(
    html_path: str, items: tuple[str, ...], after_heading: int, ordered: bool
) -> None:
    html = insert_list(_read_html(html_path), list(items), after_heading, ordered)
    _write_html(html_path, html)
    _emit({"ok": True})


@documents.command("insert-table")
@click.option("--html", "html_path", type=click.Path(exists=True), required=True)
@click.option("--headers", default="")
@click.option("--row", "rows", multiple=True)
@click.option("--after-heading", type=int, default=-1)
def documents_insert_table(
    html_path: str, headers: str, rows: tuple[str, ...], after_heading: int
) -> None:
    header_list = [part for part in headers.split(",") if part]
    row_list = [part.split(",") for part in rows]
    html = insert_table(_read_html(html_path), header_list, row_list, after_heading)
    _write_html(html_path, html)
    _emit({"ok": True})


@documents.command("replace-text")
@click.option("--html", "html_path", type=click.Path(exists=True), required=True)
@click.option("--find", required=True)
@click.option("--replace", required=True)
def documents_replace_text(html_path: str, find: str, replace: str) -> None:
    result = replace_text(_read_html(html_path), find, replace)
    if isinstance(result, dict):
        _emit(result)
        return
    _write_html(html_path, result)
    _emit({"ok": True})


@documents.command("delete")
@click.option("--html", "html_path", type=click.Path(exists=True), required=True)
@click.option("--slot", default="")
@click.option("--class-name", default="")
def documents_delete(html_path: str, slot: str, class_name: str) -> None:
    result = delete_block(_read_html(html_path), class_name=class_name, slot=slot)
    if isinstance(result, dict):
        _emit(result)
        return
    _write_html(html_path, result)
    _emit({"ok": True})


@documents.command("fill")
@click.option("--html", "html_path", type=click.Path(exists=True), required=True)
@click.option("--slots", required=True, help="JSON object of fill_document_slots keys")
def documents_fill(html_path: str, slots: str) -> None:
    payload = json.loads(slots)
    result = fill_document_slots(_read_html(html_path), payload)
    if result.get("html"):
        _write_html(html_path, str(result["html"]))
    _emit({k: v for k, v in result.items() if k != "html"})


@documents.command("reflow")
@click.option("--html", "html_path", type=click.Path(exists=True), required=True)
def documents_reflow(html_path: str) -> None:
    html = reflow_document(_read_html(html_path))
    _write_html(html_path, html)
    _emit({"ok": True})


@documents.command("apply")
@click.option("--html", "html_path", type=click.Path(exists=True), required=True)
@click.option("--requests", required=True, help="JSON list of document commands")
def documents_apply(html_path: str, requests: str) -> None:
    payload = json.loads(requests)
    result = apply_document_commands(_read_html(html_path), payload)
    if result.get("html"):
        _write_html(html_path, str(result["html"]))
    _emit({k: v for k, v in result.items() if k != "html"})
