"""SheetsAgent tools: JSON workbook edits, formulas, dataset connector."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import BaseTool, tool
from naas_abi.agents.sheets import resolve_workbook_title
from naas_abi.agents.sheets.template_resolve import (
    qualify_sheets_template_id,
    resolve_sheets_template_id,
)
from naas_abi.tools import sheets_workbook_storage as store
from naas_abi.apps.nexus.sheets.formulas import (
    calculate_workbook,
)
from naas_abi.apps.nexus.sheets.html_io import (
    parse_workbook_html,
    serialize_workbook_html,
)
from naas_abi.apps.nexus.sheets.model import SheetTab, SheetWorkbook
from naas_abi_core.services.agent.context import (
    agent_user_id,
    note_sheets_write,
    sheets_active_slug,
    sheets_active_title,
    sheets_brief,
)


def _load_model(slug: str) -> tuple[SheetWorkbook, str, str] | dict[str, Any]:
    html, source = store.load_workbook_text(slug)
    if isinstance(html, dict):
        return html
    try:
        return parse_workbook_html(html), html, source
    except ValueError as exc:
        return {"error": str(exc)}


def _persist_model(
    slug: str, workbook: SheetWorkbook, html_template: str, message: str
) -> dict[str, Any]:
    new_html = serialize_workbook_html(workbook, template_html=html_template)
    return store.persist_workbook(
        slug,
        new_html,
        message,
        default_type="feat",
    )


def sheets_tools() -> list[BaseTool]:
    @tool
    def create_sheets_project(title: str, template_id: str = "") -> dict[str, Any]:
        """Create a Sheets workbook and make it the open workbook.

        For P&L / budget / runway briefs, pass template_id
        ``monthly-pnl-v1``, ``budget-vs-actuals-v1``, or ``cash-runway-v1``
        (or omit it and the server infers from the title/brief). Default blank
        is ``grid-light-v1``.
        """
        if not agent_user_id.get():
            return {"error": "No authenticated user on this agent session."}
        denied = store.require_agent_access(write=True)
        if denied:
            return denied
        clean_title = resolve_workbook_title(title, sheets_brief.get() or "")
        base = store.slugify_title(clean_title)
        if not base:
            return {"error": "title must contain letters or digits"}
        stem = resolve_sheets_template_id(
            template_id=template_id,
            title=clean_title,
            brief=sheets_brief.get() or title or "",
        )
        qualified = qualify_sheets_template_id(stem)
        try:
            sc = store.get_source_control()
            repo_id = store.ensure_coding_repo()
            taken = {b.name for b in sc.list_branches(repo_id=repo_id)}
            slug = store.unique_slug(base, taken)
            sheets_active_title.set(clean_title)
            paths = store.ensure_sheets_write_paths(slug, template_id=qualified)
            if paths.get("error"):
                return {"error": paths["error"]}
            seed = store.load_seed_workbook_html(stem)
            if not seed:
                return {"error": "Sheets template is missing; cannot seed a workbook."}
            commit = sc.upsert_file(
                repo_id=repo_id,
                path=paths["workbook_path"],
                content=store.seed_workbook_with_title(seed, clean_title),
                message=f"feat(sheets): create {slug} from {stem}",
                branch=paths["branch"],
                **store.agent_author(),
            )
            sheets_active_slug.set(slug)
            store.remember_active_slug(slug)
            return {
                "ok": True,
                "slug": slug,
                "title": clean_title,
                "path": paths["workbook_path"],
                "template_id": qualified,
                "commit_sha": commit.sha,
                "hint": (
                    "Finance seed loaded. Edit Assumptions inputs; keep formula "
                    "cells as formulas. Confirm Checks tab Status = OK."
                    if stem != "grid-light-v1"
                    else "Blank workbook seeded. Build with formulas, not pasted totals."
                ),
            }
        except Exception as exc:  # noqa: BLE001
            return store.tool_error(exc)

    @tool
    def read_sheets_workbook(slug: str = "") -> dict[str, Any]:
        """Read the JSON sheet model (tabs, rows). Omit slug when a workbook is open."""
        if not agent_user_id.get():
            return {"error": "No authenticated user on this agent session."}
        resolved = store.resolve_slug(slug)
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
        """Replace the workbook JSON model. Prefer update_sheets_cells for bounded edits."""
        if not agent_user_id.get():
            return {"error": "No authenticated user on this agent session."}
        resolved = store.resolve_slug(slug)
        if isinstance(resolved, dict):
            return resolved
        try:
            data = json.loads(workbook_json)
            workbook = SheetWorkbook.model_validate(data)
        except (json.JSONDecodeError, ValueError) as exc:
            return {"error": f"invalid workbook_json: {exc}"}
        html, _src = store.load_workbook_text(resolved)
        if isinstance(html, dict):
            return html
        result = _persist_model(resolved, workbook, html, message)
        if "error" not in result:
            note_sheets_write("workbook")
            result["ok"] = True
        return result

    @tool
    def update_sheets_cells(
        sheet_name: str, cells_json: str, slug: str = ""
    ) -> dict[str, Any]:
        """Edit explicit A1 cells without replacing other data. cells_json: {"B2": 42, "C2": "=B2*2"}."""
        from naas_abi.apps.nexus.sheets.cell_edits import update_cells

        if not agent_user_id.get():
            return {"error": "No authenticated user on this agent session."}
        resolved = store.resolve_slug(slug)
        if isinstance(resolved, dict):
            return resolved
        loaded = _load_model(resolved)
        if isinstance(loaded, dict):
            return loaded
        workbook, html, _source = loaded
        try:
            edits = json.loads(cells_json)
            if not isinstance(edits, dict):
                raise TypeError("cells_json must be an object keyed by A1 address")
            updated = update_cells(workbook, sheet_name, edits)
        except (ValueError, TypeError) as exc:
            return {"error": str(exc)}
        result = _persist_model(
            resolved, updated, html, f"feat(sheets): edit {sheet_name} cells"
        )
        if "error" not in result:
            note_sheets_write("workbook")
            result.update(ok=True, cells_updated=len(edits))
        return result

    @tool
    def evaluate_sheets_formulas(slug: str = "") -> dict[str, Any]:
        """Evaluate ``=`` formulas for a sanity check. Does not overwrite formula cells."""
        if not agent_user_id.get():
            return {"error": "No authenticated user on this agent session."}
        resolved = store.resolve_slug(slug)
        if isinstance(resolved, dict):
            return resolved
        loaded = _load_model(resolved)
        if isinstance(loaded, dict) and "error" in loaded:
            return loaded
        workbook, _html, source = loaded
        try:
            evaluated, errors = calculate_workbook(workbook)
        except ValueError as exc:
            return {"error": str(exc)}
        checks: list[dict[str, Any]] = []
        for tab in evaluated.sheets:
            if tab.name.lower() not in {"checks", "tie-out", "tieout"}:
                continue
            for row in tab.rows[1:]:
                if not row:
                    continue
                checks.append(
                    {
                        "check": row[0] if len(row) > 0 else "",
                        "status": row[4] if len(row) > 4 else row[-1],
                    }
                )
        return {
            "ok": len(errors) == 0
            and all(check["status"] != "BREAK" for check in checks),
            "slug": resolved,
            "source": source,
            "errors": errors,
            "checks": checks,
            "note": "Formulas left intact in workbook.html; this is a read-only check.",
        }

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
        resolved = store.resolve_slug(slug)
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
        update_sheets_cells,
        evaluate_sheets_formulas,
        import_dataset_to_sheet,
    ]
