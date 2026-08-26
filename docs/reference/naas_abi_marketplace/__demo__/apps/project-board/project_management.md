# Project Management Board (`project_management.py`)

## What it is
- A **Streamlit** dashboard script for **multi-team project tracking** with multiple views:
  - Kanban board
  - Timeline (Gantt-like) view
  - Resource allocation view
  - Sprint planning view
- Includes a sidebar action to render a local **`SOP.md`** page.

## Public API
This module is a **Streamlit app script** (UI runs at import/execution). It is not structured as a reusable library.

- `load_project_data() -> pandas.DataFrame`
  - Streamlit-cached via `@st.cache_data`.
  - Generates mock data for 15 projects with fields:
    - `Project_ID`, `Title`, `Status`, `Priority`, `Team`, `Assignee`
    - `Start_Date`, `Due_Date`, `Progress`, `Story_Points`
    - computed `Days_Remaining`

## Configuration/Dependencies
- **Dependencies**
  - `streamlit`
  - `pandas`
  - `numpy`
  - `plotly.express`, `plotly.graph_objects`
- **Streamlit page config**
  - `st.set_page_config(page_title="Project Board", page_icon="📋", layout="wide")`
- **Environment**
  - When executed as `__main__`, sets `STREAMLIT_SERVER_PORT=8503`.
- **Local file**
  - Expects `SOP.md` in the same directory as `project_management.py` for the SOP page.

## Usage
Run with Streamlit:
```bash
streamlit run libs/naas-abi-marketplace/naas_abi_marketplace/__demo__/apps/project-board/project_management.py
```

In the UI:
- Sidebar controls:
  - **Project Filter** (selectbox)
  - **Team Filter** (multiselect; used to filter data)
  - **View Mode** (Kanban / Timeline / Resource / Sprint)
  - **📖 View SOP** button loads `SOP.md` into a separate page state
- Main area includes summary metrics, selected view, project actions, details table, risk analysis, blocked list, and activity feed.

## Caveats
- Data is **random/mock** on generation; no external integrations are performed (e.g., “Sync with Jira” only shows a message).
- `Project Filter` is defined but **not applied** to the dataset; only `Team Filter` affects `filtered_projects`.
- SOP rendering requires `SOP.md`; missing file displays an in-app error.
- Sprint metrics:
  - Completion rate divides by `total_points`; if `total_points` is `0` (possible after filtering), it can raise a division error.
