"""Nexus Slides commands. Parity with the Slides UI and SlidesAgent tools."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import click

from .nexus_client import (
    NexusApiError,
    build_client,
    common_api_options,
    print_json,
    print_table,
)

DEFAULT_SLIDES_TEMPLATE_ID = "abi/minimal-light-v1"

SLIDES_COMMANDS = (
    "apply-template",
    "archive",
    "asset",
    "chat",
    "create",
    "delete-slide",
    "diff",
    "duplicate",
    "export",
    "get",
    "history",
    "insert",
    "list",
    "move",
    "outline",
    "pull",
    "push",
    "read-section",
    "rename",
    "replace",
    "runtime",
    "save-to-drive",
    "templates",
    "tree",
    "unarchive",
    "version",
    "write-section",
    "write-sections",
)

_LAYOUTS = ["content", "cover", "section-divider"]


def _workspace(workspace_id: str | None) -> str:
    ws = (workspace_id or "").strip()
    if not ws:
        raise click.ClickException("Provide --workspace or set NEXUS_WORKSPACE_ID.")
    return ws


def _qs(workspace_id: str, extra: dict[str, Any] | None = None) -> str:
    query: dict[str, Any] = {"workspace_id": workspace_id}
    if extra:
        query.update({k: v for k, v in extra.items() if v is not None})
    return urlencode(query)


def _project_path(slug: str, suffix: str = "") -> str:
    return f"/api/slides/projects/{slug}{suffix}"


def _call(
    *,
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    dry_run: bool,
    api_url: str,
    token: str | None,
    email: str | None,
    password: str | None,
    table_cols: list[str] | None = None,
    table_title: str = "",
) -> Any:
    payload: dict[str, Any] = {"method": method, "path": path}
    if body is not None:
        payload["body"] = body
    if dry_run:
        print_json(payload)
        return None
    client = build_client(api_url=api_url, token=token, email=email, password=password)
    try:
        if method == "GET":
            result = client.get(path)
        elif method == "POST":
            result = client.post(path, body)
        elif method == "PATCH":
            result = client.patch(path, body or {})
        elif method == "PUT":
            result = client.request("PUT", path, json_body=body)
        else:
            raise click.ClickException(f"Unsupported method {method}")
    except NexusApiError as exc:
        raise click.ClickException(str(exc)) from exc
    if table_cols and isinstance(result, list):
        print_table(result, table_cols, title=table_title)
        return result
    print_json(result)
    return result


@click.group("slides")
def slides() -> None:
    """Manage Nexus Slides decks via the authenticated API.

    Gallery, editor, exports, git history, and the Slides agent pane.
    """


@slides.command("list")
@click.option("--archived", is_flag=True, default=False, help="Show archived decks only.")
@click.option("--all", "show_all", is_flag=True, default=False, help="Show active and archived.")
@click.option("-w", "--workspace", "workspace_id", envvar="NEXUS_WORKSPACE_ID", default=None)
@common_api_options
def slides_list(
    archived: bool,
    show_all: bool,
    workspace_id: str | None,
    api_url: str,
    token: str | None,
    email: str | None,
    password: str | None,
    dry_run: bool,
) -> None:
    """List decks (list_slides_projects)."""
    ws = _workspace(workspace_id)
    path = f"/api/slides/projects?{_qs(ws)}"
    if dry_run:
        print_json({"method": "GET", "path": path})
        return
    client = build_client(api_url=api_url, token=token, email=email, password=password)
    try:
        rows = client.get(path)
    except NexusApiError as exc:
        raise click.ClickException(str(exc)) from exc
    if not isinstance(rows, list):
        print_json(rows)
        return
    if not show_all:
        want_archived = archived
        rows = [row for row in rows if bool(row.get("archived")) == want_archived]
    print_table(
        rows,
        ["slug", "title", "template_id", "archived", "updated_at"],
        title="Slides",
    )


@slides.command("get")
@click.argument("slug")
@click.option("-w", "--workspace", "workspace_id", envvar="NEXUS_WORKSPACE_ID", default=None)
@common_api_options
def slides_get(
    slug: str,
    workspace_id: str | None,
    api_url: str,
    token: str | None,
    email: str | None,
    password: str | None,
    dry_run: bool,
) -> None:
    """Fetch project metadata for a slug."""
    ws = _workspace(workspace_id)
    _call(
        method="GET",
        path=f"{_project_path(slug)}?{_qs(ws)}",
        dry_run=dry_run,
        api_url=api_url,
        token=token,
        email=email,
        password=password,
    )


@slides.command("create")
@click.option("--title", default="Untitled presentation", help="Deck title.")
@click.option("--slug", default=None, help="URL-safe slug. Generated from the title when omitted.")
@click.option(
    "--template",
    "template_id",
    default=DEFAULT_SLIDES_TEMPLATE_ID,
    show_default=True,
    help="Seed template id.",
)
@click.option("-w", "--workspace", "workspace_id", envvar="NEXUS_WORKSPACE_ID", default=None)
@common_api_options
def slides_create(
    title: str,
    slug: str | None,
    template_id: str,
    workspace_id: str | None,
    api_url: str,
    token: str | None,
    email: str | None,
    password: str | None,
    dry_run: bool,
) -> None:
    """New presentation (create_slides_project)."""
    ws = _workspace(workspace_id)
    body: dict[str, Any] = {
        "workspace_id": ws,
        "title": title,
        "template_id": template_id,
    }
    if slug:
        body["slug"] = slug
    _call(
        method="POST",
        path="/api/slides/projects",
        body=body,
        dry_run=dry_run,
        api_url=api_url,
        token=token,
        email=email,
        password=password,
    )


@slides.command("rename")
@click.argument("slug")
@click.option("--title", required=True, help="New deck title.")
@click.option("-w", "--workspace", "workspace_id", envvar="NEXUS_WORKSPACE_ID", default=None)
@common_api_options
def slides_rename(
    slug: str,
    title: str,
    workspace_id: str | None,
    api_url: str,
    token: str | None,
    email: str | None,
    password: str | None,
    dry_run: bool,
) -> None:
    """PATCH project title."""
    ws = _workspace(workspace_id)
    _call(
        method="PATCH",
        path=_project_path(slug),
        body={"workspace_id": ws, "title": title},
        dry_run=dry_run,
        api_url=api_url,
        token=token,
        email=email,
        password=password,
    )


@slides.command("archive")
@click.argument("slug")
@click.option("-w", "--workspace", "workspace_id", envvar="NEXUS_WORKSPACE_ID", default=None)
@common_api_options
def slides_archive(
    slug: str,
    workspace_id: str | None,
    api_url: str,
    token: str | None,
    email: str | None,
    password: str | None,
    dry_run: bool,
) -> None:
    """Hide a deck from the gallery."""
    ws = _workspace(workspace_id)
    _call(
        method="PATCH",
        path=_project_path(slug),
        body={"workspace_id": ws, "archived": True},
        dry_run=dry_run,
        api_url=api_url,
        token=token,
        email=email,
        password=password,
    )


@slides.command("unarchive")
@click.argument("slug")
@click.option("-w", "--workspace", "workspace_id", envvar="NEXUS_WORKSPACE_ID", default=None)
@common_api_options
def slides_unarchive(
    slug: str,
    workspace_id: str | None,
    api_url: str,
    token: str | None,
    email: str | None,
    password: str | None,
    dry_run: bool,
) -> None:
    """Restore an archived deck."""
    ws = _workspace(workspace_id)
    _call(
        method="PATCH",
        path=_project_path(slug),
        body={"workspace_id": ws, "archived": False},
        dry_run=dry_run,
        api_url=api_url,
        token=token,
        email=email,
        password=password,
    )


@slides.command("templates")
@click.option("-w", "--workspace", "workspace_id", envvar="NEXUS_WORKSPACE_ID", default=None)
@common_api_options
def slides_templates(
    workspace_id: str | None,
    api_url: str,
    token: str | None,
    email: str | None,
    password: str | None,
    dry_run: bool,
) -> None:
    """List seed templates."""
    ws = _workspace(workspace_id)
    _call(
        method="GET",
        path=f"/api/slides/templates?{_qs(ws)}",
        dry_run=dry_run,
        api_url=api_url,
        token=token,
        email=email,
        password=password,
        table_cols=["id", "name", "description"],
        table_title="Slides templates",
    )


@slides.command("apply-template")
@click.argument("slug")
@click.option("--template", "template_id", required=True, help="Seed template id.")
@click.option("-w", "--workspace", "workspace_id", envvar="NEXUS_WORKSPACE_ID", default=None)
@common_api_options
def slides_apply_template(
    slug: str,
    template_id: str,
    workspace_id: str | None,
    api_url: str,
    token: str | None,
    email: str | None,
    password: str | None,
    dry_run: bool,
) -> None:
    """Seed an existing deck from a template."""
    ws = _workspace(workspace_id)
    _call(
        method="POST",
        path=_project_path(slug, "/apply-template"),
        body={"workspace_id": ws, "template_id": template_id},
        dry_run=dry_run,
        api_url=api_url,
        token=token,
        email=email,
        password=password,
    )


@slides.command("tree")
@click.argument("slug")
@click.option("-w", "--workspace", "workspace_id", envvar="NEXUS_WORKSPACE_ID", default=None)
@common_api_options
def slides_tree(
    slug: str,
    workspace_id: str | None,
    api_url: str,
    token: str | None,
    email: str | None,
    password: str | None,
    dry_run: bool,
) -> None:
    """Project file tree."""
    ws = _workspace(workspace_id)
    _call(
        method="GET",
        path=f"{_project_path(slug, '/tree')}?{_qs(ws)}",
        dry_run=dry_run,
        api_url=api_url,
        token=token,
        email=email,
        password=password,
    )


@slides.command("outline")
@click.argument("slug")
@click.option("-w", "--workspace", "workspace_id", envvar="NEXUS_WORKSPACE_ID", default=None)
@common_api_options
def slides_outline(
    slug: str,
    workspace_id: str | None,
    api_url: str,
    token: str | None,
    email: str | None,
    password: str | None,
    dry_run: bool,
) -> None:
    """Section index, id, title (list_slides_sections)."""
    ws = _workspace(workspace_id)
    _call(
        method="GET",
        path=f"{_project_path(slug, '/slides')}?{_qs(ws)}",
        dry_run=dry_run,
        api_url=api_url,
        token=token,
        email=email,
        password=password,
    )


@slides.command("pull")
@click.argument("slug")
@click.option("-o", "--out", "out_path", default=None, help="Write HTML to this file.")
@click.option("--include-assets", is_flag=True, default=False, help="Kept for SlidesAgent parity.")
@click.option("-w", "--workspace", "workspace_id", envvar="NEXUS_WORKSPACE_ID", default=None)
@common_api_options
def slides_pull(
    slug: str,
    out_path: str | None,
    include_assets: bool,
    workspace_id: str | None,
    api_url: str,
    token: str | None,
    email: str | None,
    password: str | None,
    dry_run: bool,
) -> None:
    """Read deck HTML (read_slides_deck)."""
    del include_assets
    ws = _workspace(workspace_id)
    path = f"{_project_path(slug, '/deck')}?{_qs(ws)}"
    if dry_run:
        print_json({"method": "GET", "path": path, "out": out_path})
        return
    result = _call(
        method="GET",
        path=path,
        dry_run=False,
        api_url=api_url,
        token=token,
        email=email,
        password=password,
    )
    if out_path and isinstance(result, dict) and result.get("html"):
        from pathlib import Path

        Path(out_path).write_text(str(result["html"]), encoding="utf-8")


@slides.command("push")
@click.argument("slug")
@click.option("-f", "--file", "file_path", required=True, type=click.Path())
@click.option("-m", "--message", default="chore(deck): update slides deck")
@click.option("-w", "--workspace", "workspace_id", envvar="NEXUS_WORKSPACE_ID", default=None)
@common_api_options
def slides_push(
    slug: str,
    file_path: str,
    message: str,
    workspace_id: str | None,
    api_url: str,
    token: str | None,
    email: str | None,
    password: str | None,
    dry_run: bool,
) -> None:
    """Write full deck HTML (write_slides_deck)."""
    from pathlib import Path

    ws = _workspace(workspace_id)
    html = Path(file_path).read_text(encoding="utf-8") if not dry_run else f"<{file_path}>"
    _call(
        method="PUT",
        path=_project_path(slug, "/deck"),
        body={"workspace_id": ws, "html": html, "message": message},
        dry_run=dry_run,
        api_url=api_url,
        token=token,
        email=email,
        password=password,
    )


@slides.command("read-section")
@click.argument("slug")
@click.option("--index", type=int, default=None)
@click.option("--section-id", default=None)
@click.option("-w", "--workspace", "workspace_id", envvar="NEXUS_WORKSPACE_ID", default=None)
@common_api_options
def slides_read_section(
    slug: str,
    index: int | None,
    section_id: str | None,
    workspace_id: str | None,
    api_url: str,
    token: str | None,
    email: str | None,
    password: str | None,
    dry_run: bool,
) -> None:
    """Read one section (read_slides_section)."""
    ws = _workspace(workspace_id)
    print_json(
        {
            "method": "GET",
            "path": f"{_project_path(slug, '/deck')}?{_qs(ws)}",
            "index": index,
            "section_id": section_id,
            "note": "Agent parity: GET deck then extract one <section>.",
        }
    )
    if not dry_run:
        raise click.ClickException("read-section live extract is not wired. Use pull.")


@slides.command("write-section")
@click.argument("slug")
@click.option("--index", type=int, default=None)
@click.option("--section-id", default=None)
@click.option("-f", "--file", "file_path", required=True, type=click.Path())
@click.option("-m", "--message", default="refactor(slides): rewrite section via abi")
@click.option("-w", "--workspace", "workspace_id", envvar="NEXUS_WORKSPACE_ID", default=None)
@common_api_options
def slides_write_section(
    slug: str,
    index: int | None,
    section_id: str | None,
    file_path: str,
    message: str,
    workspace_id: str | None,
    api_url: str,
    token: str | None,
    email: str | None,
    password: str | None,
    dry_run: bool,
) -> None:
    """Replace one slide (write_slides_section)."""
    ws = _workspace(workspace_id)
    print_json(
        {
            "method": "PUT",
            "path": _project_path(slug, "/deck"),
            "body": {
                "workspace_id": ws,
                "file": file_path,
                "index": index,
                "section_id": section_id,
                "message": message,
            },
            "note": "Agent parity: GET deck, replace one <section>, PUT.",
        }
    )
    if not dry_run:
        raise click.ClickException("write-section live mutate is not wired. Use pull / push.")


@slides.command("write-sections")
@click.argument("slug")
@click.option("-f", "--file", "file_path", required=True, type=click.Path())
@click.option("-m", "--message", default="refactor(slides): rewrite sections via abi")
@click.option("-w", "--workspace", "workspace_id", envvar="NEXUS_WORKSPACE_ID", default=None)
@common_api_options
def slides_write_sections(
    slug: str,
    file_path: str,
    message: str,
    workspace_id: str | None,
    api_url: str,
    token: str | None,
    email: str | None,
    password: str | None,
    dry_run: bool,
) -> None:
    """Batch replace slides (write_slides_sections)."""
    ws = _workspace(workspace_id)
    print_json(
        {
            "method": "PUT",
            "path": _project_path(slug, "/deck"),
            "body": {"workspace_id": ws, "file": file_path, "message": message},
            "note": "Agent parity: GET deck, apply section JSON, PUT.",
        }
    )
    if not dry_run:
        raise click.ClickException("write-sections live mutate is not wired. Use pull / push.")


@slides.command("replace")
@click.argument("slug")
@click.option("--old", "old_text", required=True)
@click.option("--new", "new_text", required=True)
@click.option("--index", type=int, default=None)
@click.option("--occurrence", type=int, default=0)
@click.option("-m", "--message", default="fix(slides): replace text via abi")
@click.option("-w", "--workspace", "workspace_id", envvar="NEXUS_WORKSPACE_ID", default=None)
@common_api_options
def slides_replace(
    slug: str,
    old_text: str,
    new_text: str,
    index: int | None,
    occurrence: int,
    message: str,
    workspace_id: str | None,
    api_url: str,
    token: str | None,
    email: str | None,
    password: str | None,
    dry_run: bool,
) -> None:
    """Surgical string replace (replace_in_slides_deck)."""
    ws = _workspace(workspace_id)
    print_json(
        {
            "method": "PUT",
            "path": _project_path(slug, "/deck"),
            "body": {
                "workspace_id": ws,
                "old": old_text,
                "new": new_text,
                "index": index,
                "occurrence": occurrence,
                "message": message,
            },
            "note": "Agent parity: GET deck, replace string, PUT.",
        }
    )
    if not dry_run:
        raise click.ClickException("replace live mutate is not wired. Use pull / push.")


@slides.command("asset")
@click.argument("slug")
@click.argument("filename")
@click.option("-o", "--out", "out_path", default=None)
@click.option("-w", "--workspace", "workspace_id", envvar="NEXUS_WORKSPACE_ID", default=None)
@common_api_options
def slides_asset(
    slug: str,
    filename: str,
    out_path: str | None,
    workspace_id: str | None,
    api_url: str,
    token: str | None,
    email: str | None,
    password: str | None,
    dry_run: bool,
) -> None:
    """Download a deck asset."""
    ws = _workspace(workspace_id)
    path = f"{_project_path(slug, f'/assets/{filename}')}?{_qs(ws)}"
    print_json({"method": "GET", "path": path, "out": out_path})
    if not dry_run:
        raise click.ClickException("asset binary download is not wired. Use --dry-run.")


@slides.command("insert")
@click.argument("slug")
@click.option("--after", "after_index", type=int, default=-1, show_default=True)
@click.option("--layout", type=click.Choice(_LAYOUTS, case_sensitive=False), default="content")
@click.option("--title", default="")
@click.option("-w", "--workspace", "workspace_id", envvar="NEXUS_WORKSPACE_ID", default=None)
@common_api_options
def slides_insert(
    slug: str,
    after_index: int,
    layout: str,
    title: str,
    workspace_id: str | None,
    api_url: str,
    token: str | None,
    email: str | None,
    password: str | None,
    dry_run: bool,
) -> None:
    """Insert a slide (cover|section-divider|content)."""
    ws = _workspace(workspace_id)
    _call(
        method="POST",
        path=_project_path(slug, "/slides/insert"),
        body={
            "workspace_id": ws,
            "after_index": after_index,
            "layout": layout,
            "title": title,
        },
        dry_run=dry_run,
        api_url=api_url,
        token=token,
        email=email,
        password=password,
    )


@slides.command("duplicate")
@click.argument("slug")
@click.option("--index", required=True, type=int)
@click.option("-w", "--workspace", "workspace_id", envvar="NEXUS_WORKSPACE_ID", default=None)
@common_api_options
def slides_duplicate(
    slug: str,
    index: int,
    workspace_id: str | None,
    api_url: str,
    token: str | None,
    email: str | None,
    password: str | None,
    dry_run: bool,
) -> None:
    """Clone a slide after the source index."""
    ws = _workspace(workspace_id)
    _call(
        method="POST",
        path=_project_path(slug, "/slides/duplicate"),
        body={"workspace_id": ws, "index": index},
        dry_run=dry_run,
        api_url=api_url,
        token=token,
        email=email,
        password=password,
    )


@slides.command("delete-slide")
@click.argument("slug")
@click.option("--index", required=True, type=int)
@click.option("-w", "--workspace", "workspace_id", envvar="NEXUS_WORKSPACE_ID", default=None)
@common_api_options
def slides_delete_slide(
    slug: str,
    index: int,
    workspace_id: str | None,
    api_url: str,
    token: str | None,
    email: str | None,
    password: str | None,
    dry_run: bool,
) -> None:
    """Remove one slide; refuses the last one."""
    ws = _workspace(workspace_id)
    _call(
        method="POST",
        path=_project_path(slug, "/slides/delete"),
        body={"workspace_id": ws, "index": index},
        dry_run=dry_run,
        api_url=api_url,
        token=token,
        email=email,
        password=password,
    )


@slides.command("move")
@click.argument("slug")
@click.option("--from", "from_index", type=int, default=None)
@click.option("--to", "to_index", type=int, default=None)
@click.option("--order", default=None, help="JSON list of indexes, e.g. [0,2,1].")
@click.option("-w", "--workspace", "workspace_id", envvar="NEXUS_WORKSPACE_ID", default=None)
@common_api_options
def slides_move(
    slug: str,
    from_index: int | None,
    to_index: int | None,
    order: str | None,
    workspace_id: str | None,
    api_url: str,
    token: str | None,
    email: str | None,
    password: str | None,
    dry_run: bool,
) -> None:
    """Reorder slides (reorder_slides)."""
    import json

    ws = _workspace(workspace_id)
    body: dict[str, Any] = {"workspace_id": ws}
    if order:
        parsed = json.loads(order)
        if not isinstance(parsed, list):
            raise click.ClickException("--order must be a JSON list of indexes.")
        body["order"] = parsed
    else:
        if from_index is None or to_index is None:
            raise click.ClickException("Provide --from and --to, or --order.")
        body["from_index"] = from_index
        body["to_index"] = to_index
    _call(
        method="POST",
        path=_project_path(slug, "/slides/reorder"),
        body=body,
        dry_run=dry_run,
        api_url=api_url,
        token=token,
        email=email,
        password=password,
    )


@slides.command("version")
@click.argument("slug")
@click.option("-w", "--workspace", "workspace_id", envvar="NEXUS_WORKSPACE_ID", default=None)
@common_api_options
def slides_version(
    slug: str,
    workspace_id: str | None,
    api_url: str,
    token: str | None,
    email: str | None,
    password: str | None,
    dry_run: bool,
) -> None:
    """0.x semver from Conventional Commits."""
    ws = _workspace(workspace_id)
    _call(
        method="GET",
        path=f"{_project_path(slug, '/version')}?{_qs(ws)}",
        dry_run=dry_run,
        api_url=api_url,
        token=token,
        email=email,
        password=password,
    )


@slides.command("history")
@click.argument("slug")
@click.option("--limit", type=int, default=20, show_default=True)
@click.option("-w", "--workspace", "workspace_id", envvar="NEXUS_WORKSPACE_ID", default=None)
@common_api_options
def slides_history(
    slug: str,
    limit: int,
    workspace_id: str | None,
    api_url: str,
    token: str | None,
    email: str | None,
    password: str | None,
    dry_run: bool,
) -> None:
    """List commits on the deck branch (slides_history)."""
    ws = _workspace(workspace_id)
    _call(
        method="GET",
        path=f"{_project_path(slug, '/history')}?{_qs(ws, {'limit': limit})}",
        dry_run=dry_run,
        api_url=api_url,
        token=token,
        email=email,
        password=password,
        table_cols=["sha", "version", "message", "author", "date"],
        table_title="Slides history",
    )


@slides.command("diff")
@click.argument("slug")
@click.option("--base", required=True, help="Baseline commit SHA.")
@click.option("--head", default=None, help="Head SHA. Branch tip when omitted.")
@click.option("-w", "--workspace", "workspace_id", envvar="NEXUS_WORKSPACE_ID", default=None)
@common_api_options
def slides_diff(
    slug: str,
    base: str,
    head: str | None,
    workspace_id: str | None,
    api_url: str,
    token: str | None,
    email: str | None,
    password: str | None,
    dry_run: bool,
) -> None:
    """Files changed between two commits."""
    ws = _workspace(workspace_id)
    extra: dict[str, Any] = {"base": base}
    if head:
        extra["head"] = head
    _call(
        method="GET",
        path=f"{_project_path(slug, '/history/diff')}?{_qs(ws, extra)}",
        dry_run=dry_run,
        api_url=api_url,
        token=token,
        email=email,
        password=password,
    )


@slides.command("runtime")
@click.argument("slug")
@click.option("-w", "--workspace", "workspace_id", envvar="NEXUS_WORKSPACE_ID", default=None)
@common_api_options
def slides_runtime(
    slug: str,
    workspace_id: str | None,
    api_url: str,
    token: str | None,
    email: str | None,
    password: str | None,
    dry_run: bool,
) -> None:
    """Ensure the Coder sidecar for a deck."""
    ws = _workspace(workspace_id)
    _call(
        method="POST",
        path=f"{_project_path(slug, '/runtime')}?{_qs(ws)}",
        body=None,
        dry_run=dry_run,
        api_url=api_url,
        token=token,
        email=email,
        password=password,
    )


@slides.command("export")
@click.argument("slug")
@click.option("--format", "fmt", type=click.Choice(["html", "pptx", "pdf"], case_sensitive=False), required=True)
@click.option("-o", "--out", "out_path", required=True, type=click.Path())
@click.option("-w", "--workspace", "workspace_id", envvar="NEXUS_WORKSPACE_ID", default=None)
@common_api_options
def slides_export(
    slug: str,
    fmt: str,
    out_path: str,
    workspace_id: str | None,
    api_url: str,
    token: str | None,
    email: str | None,
    password: str | None,
    dry_run: bool,
) -> None:
    """Write html, pptx, or pdf to a file."""
    ws = _workspace(workspace_id)
    if fmt.lower() != "html":
        print_json(
            {
                "method": None,
                "path": None,
                "format": fmt,
                "out": out_path,
                "error": f"{fmt} export is browser-only. There is no API yet.",
            }
        )
        if not dry_run:
            raise click.ClickException(f"{fmt} export is browser-only. There is no API yet.")
        return
    path = f"{_project_path(slug, '/deck')}?{_qs(ws)}"
    if dry_run:
        print_json({"method": "GET", "path": path, "format": "html", "out": out_path})
        return
    result = _call(
        method="GET",
        path=path,
        dry_run=False,
        api_url=api_url,
        token=token,
        email=email,
        password=password,
    )
    if isinstance(result, dict) and result.get("html"):
        from pathlib import Path

        Path(out_path).write_text(str(result["html"]), encoding="utf-8")


@slides.command("save-to-drive")
@click.argument("slug")
@click.option("-w", "--workspace", "workspace_id", envvar="NEXUS_WORKSPACE_ID", default=None)
@common_api_options
def slides_save_to_drive(
    slug: str,
    workspace_id: str | None,
    api_url: str,
    token: str | None,
    email: str | None,
    password: str | None,
    dry_run: bool,
) -> None:
    """Copy deck.html to My Drive."""
    ws = _workspace(workspace_id)
    print_json(
        {
            "method": "POST",
            "path": "/api/files/upload",
            "body": {
                "scope": "my_drive",
                "path": f"slides/{slug}",
                "workspace_id": ws,
                "files": ["deck.html", "project.json"],
            },
        }
    )
    if not dry_run:
        raise click.ClickException("save-to-drive multipart upload is not wired. Use --dry-run.")


@slides.command("chat")
@click.argument("slug")
@click.option("-m", "--message", default=None, help="Optional first user message.")
@click.option("-w", "--workspace", "workspace_id", envvar="NEXUS_WORKSPACE_ID", default=None)
@common_api_options
def slides_chat(
    slug: str,
    message: str | None,
    workspace_id: str | None,
    api_url: str,
    token: str | None,
    email: str | None,
    password: str | None,
    dry_run: bool,
) -> None:
    """Open the Slides agent on a slug."""
    ws = _workspace(workspace_id)
    print_json(
        {
            "agent": "SlidesAgent",
            "slug": slug,
            "workspace_id": ws,
            "message": message,
            "note": "Binds slides_active_slug the way the Slides pane does.",
        }
    )
    if not dry_run:
        raise click.ClickException("slides chat is not wired. Use --dry-run.")
