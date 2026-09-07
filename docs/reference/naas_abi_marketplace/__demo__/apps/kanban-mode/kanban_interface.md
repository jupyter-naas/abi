# `kanban_interface.py`

## What it is
- A **Streamlit** demo app that renders a Kanban-style task board with:
  - SOP viewer page (renders a local `SOP.md`)
  - Sidebar configuration (board name, workflow type)
  - Column add/delete (keeps at least 2 columns)
  - Task filtering (assignee, priority, tags)
  - Task movement between columns via left/right buttons
  - Task creation form
  - Basic analytics (Plotly bar + pie charts)
  - Import/export board data as JSON

## Public API
This file is a **Streamlit script** (top-level execution). No reusable functions/classes are defined.

Operator-facing behaviors driven by UI actions:
- **Routing**
  - Sidebar button **“📖 View SOP”** sets `st.session_state.page = "sop"` and reruns.
  - SOP page **“← Back to Kanban”** sets `page = "main"` and reruns.
- **Session state keys**
  - `page`: `"main"` (default) or `"sop"`
  - `kanban_tasks`: list of task dicts (initialized with sample data)
  - `kanban_columns`: list of column names (initialized to `["To Do", "In Progress", "Review", "Done"]`)
  - `editing_task`: set to a task id when clicking ✏️ (no edit UI implemented)
- **Columns**
  - Add column via sidebar **“➕ Add Column”** + `text_input(key="new_column")`.
  - Delete column via 🗑️ (only if more than 2 columns); tasks in deleted column are moved to the first column.
- **Filters**
  - Assignee (single select, includes `"All"`)
  - Priority (single select: `"All"`, `"High"`, `"Medium"`, `"Low"`)
  - Tags (multi-select)
- **Tasks**
  - Move task left/right via **⬅️ / ➡️** (updates `task["status"]` in `st.session_state.kanban_tasks` and reruns).
  - Create task via expander form; appends to `kanban_tasks` and reruns.
- **Analytics**
  - Bar chart: tasks by status (based on current filters)
  - Pie chart: tasks by assignee (shown only if there is data)
- **Data management**
  - Export: builds JSON with `json.dumps(..., default=str)` and offers a download button.
  - Import: uploads JSON; sets `kanban_columns`/`kanban_tasks`; converts `task["created"]` from string using `datetime.fromisoformat`.
- **Quick actions**
  - Reset demo data: deletes `kanban_tasks` and `kanban_columns` from session state and reruns.
  - Generate report: placeholder info message only.

## Configuration/Dependencies
- **Packages**
  - `streamlit`
  - `plotly.express`
- **Standard library**
  - `datetime` (`datetime`, `timedelta`)
  - `json`, `os`
- **Streamlit page configuration**
  - `st.set_page_config(page_title="Kanban Mode", page_icon="📋", layout="wide")`
- **Port**
  - When executed as `__main__`, sets `os.environ["STREAMLIT_SERVER_PORT"] = "8517"`.

## Usage
Run the app with Streamlit:

```bash
streamlit run libs/naas-abi-marketplace/naas_abi_marketplace/__demo__/apps/kanban-mode/kanban_interface.py
```

Optional SOP file location (rendered when using “📖 View SOP”):

```text
libs/naas-abi-marketplace/naas_abi_marketplace/__demo__/apps/kanban-mode/SOP.md
```

## Caveats
- No drag-and-drop: task movement is **button-based** (⬅️ / ➡️) only.
- ✏️ “Edit task” only sets `st.session_state.editing_task`; no edit form is implemented.
- Import expects JSON with keys: `"columns"` and `"tasks"` (and optionally `"board_name"`). `created` must be ISO-format if provided as a string (`datetime.fromisoformat`).
- Column add flow depends on Streamlit reruns: the “New Column Name” input appears after pressing “➕ Add Column” and may require an extra interaction cycle.
