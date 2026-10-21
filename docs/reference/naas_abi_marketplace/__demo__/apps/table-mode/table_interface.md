# table_interface

## What it is
- A **Streamlit** demo app implementing a “Table Mode Interface Pattern”:
  - Structured data grid with **search**, **filters**, **pagination**, multiple **view modes**, quick **charts**, and basic **export** controls.
- Includes a sidebar **SOP viewer** that renders `SOP.md` from the same directory.

## Public API
This module is a **Streamlit script** (UI executed at import/run time), not a library-style module.

- `load_sample_data() -> pandas.DataFrame`
  - Cached with `@st.cache_data`.
  - Generates deterministic sample data (200 rows) including columns: `ID`, `Date`, `Category`, `Title`, `Status`, `Priority`, `Assigned_To`, `Progress`, `Budget`, `Hours_Spent`, `Due_Date`.

Other externally visible behavior (via Streamlit widgets/state):
- `st.session_state.page` routing:
  - `"main"`: table UI
  - `"sop"`: SOP markdown display page

## Configuration/Dependencies
### Runtime dependencies
- `streamlit`
- `pandas`
- `numpy`
- `plotly.express`

### Streamlit configuration
- `st.set_page_config(page_title="Table Mode", page_icon="📊", layout="wide")`
- When run as `__main__`:
  - Sets `os.environ["STREAMLIT_SERVER_PORT"] = "8522"`

### Data sources (as implemented)
- **Sample Data**: uses `load_sample_data()`
- **Upload CSV**: `st.sidebar.file_uploader(..., type="csv")` + `pd.read_csv()`
- **Database Connection / API Endpoint**: placeholders; fall back to sample data with an info message

## Usage
Run with Streamlit (path relative to repo root):

```bash
streamlit run libs/naas-abi-marketplace/naas_abi_marketplace/__demo__/apps/table-mode/table_interface.py
```

In the UI:
- Use **Filters & Search**: text search (all columns), `Category`, `Status`, `Date Range` (when those columns exist).
- Choose **View Mode**:
  - Standard Table (`st.dataframe`)
  - Editable Grid (`st.data_editor`)
  - Summary View (grouped by `Category`)
  - Pivot Table (configurable index/columns/values; mean aggregation)
- Use **Quick Visualizations** (when columns exist):
  - Category pie chart
  - Progress histogram
- Use **Quick Actions** in the sidebar:
  - Refresh Data (clears cache and reruns)
  - Generate Report / Advanced Search (placeholders)

## Caveats
- Database/API sources are **not implemented**; they always fall back to sample data.
- “Download Excel” and “Copy to Clipboard” are **placeholders** (info messages only).
- Editable Grid changes are **not persisted** beyond the current rerun/session.
- SOP page requires `SOP.md` in the same directory; otherwise an error is shown.
- Date filtering uses `filtered_df['Date'].dt.date`; uploaded CSVs must have a datetime-like `Date` column or filtering may error.
