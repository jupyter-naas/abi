# `kanban_interface.py`

## What it is
- A **Streamlit** demo app implementing a Kanban-style task board.
- Provides:
  - Sidebar configuration (board name, workflow type, columns)
  - Task filtering (assignee, priority, tags)
  - Basic task movement between columns (left/right)
  - Task creation
  - Simple analytics charts (Plotly)
  - Import/export of board data as JSON
  - An SOP viewer page that renders a local `SOP.md`

## Public API
This file is a **Streamlit script** (no reusable public functions/classes are defined). Behavior is driven by top-level execution.

Key UI actions (operator-facing behaviors):
- **SOP routing**
  - Sidebar button **“📖 View SOP”** sets `st.session_state.page = "sop"` and reruns.
  - SOP page loads and displays `SOP.md` from the same directory (if present).
- **Board configuration**
  - Board name (`text_input`)
  - Workflow type (`selectbox`)
- **Column management**
  - Add column via sidebar button and a `text_input` (uses key `"new_column"`).
  - Delete a column (keeps at least 2 columns); tasks in a deleted column are moved to the first column.
- **Filtering**
  - Assignee (single select), priority (single select), tags (multi-select).
- **Task operations**
  - Move task left/right via arrow buttons (updates `task["status"]` and reruns).
  - Create new task via expander form; appends to `st.session_state.kanban_tasks`.
  - “Edit” button sets `st.session_state.editing_task` to the task id (no further edit UI implemented).
- **Analytics**
  - Bar chart: tasks by status
  - Pie chart: tasks by assignee (only shown if there is data)
- **Data management**
  - Export: creates JSON and provides a download button.
  - Import: upload JSON; sets columns/tasks and converts `created` strings using `datetime.fromisoformat`.
- **Quick actions**
  - Reset demo data: deletes `kanban_tasks` and `kanban_columns` from session state and reruns.
  - Generate report: placeholder message only.

## Configuration/Dependencies
- **Python packages**
  - `streamlit`
  - `plotly` (uses `plotly.express as px`)
- **Standard library**
  - `datetime`, `timedelta`, `json`, `os`
- **Streamlit page config**
  - `st.set_page_config(page_title="Kanban Mode", page_icon="📋", layout="wide")`
- **Port configuration**
  - When executed as `__main__`, sets `os.environ["STREAMLIT_SERVER_PORT"] = "8517"`.

## Usage
Run with Streamlit:

```bash
streamlit run libs/naas-abi-marketplace/naas_abi_marketplace/__demo__/apps/kanban-mode/kanban_interface.py
```

Optional: ensure an SOP file exists alongside the script:

```text
libs/naas-abi-marketplace/naas_abi_marketplace/__demo__/apps/kanban-mode/SOP.md
```

## Caveats
- **No true drag-and-drop**: task movement is via left/right buttons only.
- **Edit is not implemented**: clicking ✏️ only sets `st.session_state.editing_task`.
- **Import expectations**:
  - Uploaded JSON must contain keys: `"columns"` and `"tasks"` (and optionally `"board_name"`).
  - Task `"created"` values are parsed with `datetime.fromisoformat` if they are strings; non-ISO formats may fail.
- **“Add Column” flow**: the new column name is taken from a sidebar `text_input` that appears when the add button is pressed; this interaction can be finicky due to Streamlit rerun behavior.
