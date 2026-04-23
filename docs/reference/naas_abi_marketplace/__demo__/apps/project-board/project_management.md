# Project Management Board (`project_management.py`)

## What it is
- A **Streamlit** app that renders a **Project Management Board** with multiple views:
  - Kanban board
  - Timeline (Gantt-like) view
  - Resource allocation view
  - Sprint planning view
- Includes an SOP page renderer that loads a local `SOP.md`.

## Public API
This module is a **Streamlit script** (UI executed at import/run time). It does not expose a reusable library API.

- `load_project_data() -> pandas.DataFrame`
  - Cached via `@st.cache_data`
  - Generates **sample project data** (15 projects) with random `Status`, `Priority`, `Team`, `Assignee`, `Progress`, `Story_Points`, and computed `Days_Remaining`.

## Configuration/Dependencies
- **Python packages**
  - `streamlit`
  - `pandas`
  - `numpy`
  - `plotly` (`plotly.express`, `plotly.graph_objects`)
- **Runtime configuration**
  - Calls `st.set_page_config(page_title="Project Board", page_icon="📋", layout="wide")`.
  - When executed as `__main__`, sets:
    - `os.environ["STREAMLIT_SERVER_PORT"] = "8503"`
- **Local files**
  - `SOP.md` is expected in the **same directory** as this script for the SOP page.

## Usage
Run with Streamlit:

```bash
streamlit run libs/naas-abi-marketplace/naas_abi_marketplace/__demo__/apps/project-board/project_management.py
```

In the app:
- Use sidebar controls:
  - **Project Filter** (currently not applied to data in code)
  - **Team Filter** (filters the dataset)
  - **View Mode** (switches between Kanban/Timeline/Resource/Sprint views)
- Click **📖 View SOP** to load and display `SOP.md`.

## Caveats
- Data is **mock/random** on generation; it is not connected to external systems (buttons display success/info messages only).
- `Project Filter` selection is defined but **not used** to filter `filtered_projects`.
- SOP page requires `SOP.md`; missing file triggers an in-app error message.
- The script executes UI code at module load; it is not designed to be imported as a library.
