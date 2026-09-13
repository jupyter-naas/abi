"""SheetsAgent tools: JSON workbook edits, formulas, dataset connector."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import BaseTool, tool
from naas_abi.agents.sheets import resolve_workbook_title
from naas_abi.agents.tools import sheets_tools_legacy as leg
from naas_abi.apps.nexus.sheets.formulas import evaluate_workbook_formulas
from naas_abi.apps.nexus.sheets.html_io import parse_workbook_html, serialize_workbook_html
from naas_abi.apps.nexus.sheets.model import SheetTab, SheetWorkbook
from naas_abi_core.services.agent.context import (
    agent_user_id,
    note_sheets_write,
    sheets_active_slug,
    sheets_active_title,
    sheets_brief,
)


def _load_model(slug: str) -> tuple[SheetWorkbook, str, str] | dict[str, Any]:
    html, source = leg._load_workbook_text(slug)
    if isinstance(html, dict):
        return html
    try:
        return parse_workbook_html(html), html, source
    except ValueError as exc:
        return {"error": str(exc)}


def _persist_model(slug: str, workbook: SheetWorkbook, html_template: str, message: str) -> dict[str, Any]:
    new_html = serialize_workbook_html(workbook, template_html=html_template)
    return leg._persist_workbook(slug, new_html, message, default_type="feat")


def sheets_tools() -> list[BaseTool]:
    @tool
    def create_sheets_project(title: str) -> dict[str, Any]:
        """Create a Sheets workbook (grid-light seed) and make it the open workbook."""
        if not agent_user_id.get():
            return {"error": "No authenticated user on this agent session."}
        clean_title = resolve_workbook_title(title, sheets_brief.get() or "")
        base = leg._slugify_title(clean_title)
        if not base:
            return {"error": "title must contain letters or digits"}
        try:
            sc = leg._get_source_control()
            repo_id = leg._ensure_coding_repo()
            taken = {b.name for b in sc.list_branches(repo_id=repo_id)}
            slug = leg._unique_slug(base, taken)
            sheets_active_title.set(clean_title)
            paths = leg._ensure_sheets_write_paths(slug)
            if paths.get("error"):
                return {"error": paths["error"]}
            seed = leg._load_seed_workbook_html()
            if not seed:
                return {"error": "Sheets template is missing; cannot seed a workbook."}
            commit = sc.upsert_file(
                repo_id=repo_id,
                path=paths["workbook_path"],
                content=leg._seed_deck_with_title(seed, clean_title),
                message=f"feat(sheets): create {slug}",
                branch=paths["branch"],
                **leg._agent_author(),
            )
            sheets_active_slug.set(slug)
            leg._remember_active_slug(slug)
            return {
                "ok": True,
                "slug": slug,
                "title": clean_title,
                "path": paths["workbook_path"],
                "template_id": "grid-light-v1",
                "commit_sha": commit.sha,
            }
        except Exception as exc:  # noqa: BLE001
            return leg._tool_error(exc)

    @tool
    def read_sheets_workbook(slug: str = "") -> dict[str, Any]:
        """Read the JSON sheet model (tabs, rows). Omit slug when a workbook is open."""
        if not agent_user_id.get():
            return {"error": "No authenticated user on this agent session."}
        resolved = leg._resolve_slug(slug)
        if isinstance(resolved, dict):
            return resolved
        loaded = _load_model(resolved)
        if isinstance(loaded, dict) and "error" in loaded:
            return loaded
        workbook, _html, source = loaded
        return {
            "slug": resolved,
            "source": source,
            "title": workbook.title,
            "sheets": [tab.model_dump() for tab in workbook.sheets],
        }

    @tool
    def write_sheets_workbook(
        workbook_json: str,
        slug: str = "",
        message: str = "feat(sheets): update workbook model",
    ) -> dict[str, Any]:
        """Replace the workbook JSON model. ``workbook_json`` is a SheetWorkbook object."""
        if not agent_user_id.get():
            return {"error": "No authenticated user on this agent session."}
        resolved = leg._resolve_slug(slug)
        if isinstance(resolved, dict):
            return resolved
        try:
            data = json.loads(workbook_json)
            workbook = SheetWorkbook.model_validate(data)
        except (json.JSONDecodeError, ValueError) as exc:
            return {"error": f"invalid workbook_json: {exc}"}
        html, _src = leg._load_workbook_text(resolved)
        if isinstance(html, dict):
            return html
        result = _persist_model(resolved, workbook, html, message)
        if "error" not in result:
            note_sheets_write("workbook")
            result["ok"] = True
        return result

    @tool
    def evaluate_sheets_formulas(slug: str = "") -> dict[str, Any]:
        """Evaluate ``=`` formulas in the open workbook and persist computed values."""
        if not agent_user_id.get():
            return {"error": "No authenticated user on this agent session."}
        resolved = leg._resolve_slug(slug)
        if isinstance(resolved, dict):
            return resolved
        loaded = _load_model(resolved)
        if isinstance(loaded, dict) and "error" in loaded:
            return loaded
        workbook, html, _source = loaded
        evaluated = evaluate_workbook_formulas(workbook)
        result = _persist_model(
            resolved,
            evaluated,
            html,
            "fix(sheets): evaluate formulas",
        )
        if "error" not in result:
            note_sheets_write("formulas")
            result["ok"] = True
        return result

    @tool
    def import_dataset_to_sheet(
        dataset_name: str,
        namespace: str = "default",
        sheet_name: str = "Sheet1",
        limit: int = 200,
        slug: str = "",
    ) -> dict[str, Any]:
        """Live connector: pull rows from a Nexus dataset into the open workbook."""
        if not agent_user_id.get():
            return {"error": "No authenticated user on this agent session."}
        resolved = leg._resolve_slug(slug)
        if isinstance(resolved, dict):
            return resolved
        try:
            from naas_abi import ABIModule

            engine = ABIModule.get_instance().engine
            if not engine.services.dataset_available():
                return {"error": "Dataset service is not available in this runtime."}
            ds = engine.services.dataset
            sql = f'SELECT * FROM "{namespace}"."{dataset_name}" LIMIT {int(limit)}'
            qr = ds.query(sql, namespace=namespace)
            columns = list(qr.columns)
            rows: list[list[Any]] = [columns]
            for row in qr.rows:
                rows.append([row.get(c) for c in columns])
        except Exception as exc:  # noqa: BLE001
            return {"error": f"dataset import failed: {exc}"}
        loaded = _load_model(resolved)
        if isinstance(loaded, dict) and "error" in loaded:
            return loaded
        workbook, html, _source = loaded
        tab = next((t for t in workbook.sheets if t.name == sheet_name), None)
        if tab is None:
            workbook.sheets.append(SheetTab(name=sheet_name, rows=rows))
        else:
            tab.rows = rows
        result = _persist_model(
            resolved,
            workbook,
            html,
            f"feat(sheets): import dataset {namespace}/{dataset_name}",
        )
        if "error" not in result:
            note_sheets_write(f"dataset {namespace}/{dataset_name}")
            result["ok"] = True
            result["rows_imported"] = len(rows) - 1
        return result

    return [
        create_sheets_project,
        read_sheets_workbook,
        write_sheets_workbook,
        evaluate_sheets_formulas,
        import_dataset_to_sheet,
    ]
