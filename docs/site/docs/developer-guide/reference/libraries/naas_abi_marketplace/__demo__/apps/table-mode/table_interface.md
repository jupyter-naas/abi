# table_interface

## What it is
- A **Streamlit** demo app implementing a “Table Mode Interface Pattern”:
  - Structured data grid with **search**, **filters**, **pagination**, multiple **view modes**, quick **charts**, and basic **export** controls.
- Includes a sidebar **SOP viewer** that renders `SOP.md` from the same directory.

## Public API
This module is a **Streamlit script** (UI executed at import/run time), not a library-style module.

- `load_sample_data() -> pandas.DataFrame`
  - Cached (`@st.cache_data`) generator for deterministic sample data (200 rows) with fields like `ID`, `Date`, `Category`, `Status`, `Progress`, `Budget`, etc.

Other “public” behavior is via Streamlit widgets:
- Page routing via `st.session_state.page`:
  - `"main"`: table UI
  - `"sop"`: SOP markdown display

## Configuration/Dependencies
### Runtime dependencies
- `streamlit`
- `pandas`
- `numpy`
- `plotly.express`

### App configuration
- `st.set_page_config(page_title="Table Mode", page_icon="📊", layout="wide")`
- When run as `__main__`, sets:
  - `os.environ["STREAMLIT_SERVER_PORT"] = "8522"`

### Data sources (UI)
- **Sample Data** (implemented)
- **Upload CSV** (implemented via `st.sidebar.file_uploader`; falls back to sample data if none uploaded)
- **Database Connection**, **API Endpoint** (not implemented; fall back to sample data with an info message)

## Usage
Run with Streamlit (from your repo root, adjust path as needed):

```bash
streamlit run libs/naas-abi-marketplace/naas_abi_marketplace/__demo__/apps/table-mode/table_interface.py
```

In the UI:
- Use **Filters & Search** (search term, category, status, date range).
- Choose **View Mode**:
  - Standard Table (`st.dataframe`)
  - Editable Grid (`st.data_editor`, changes not persisted)
  - Summary View (groupby `Category`)
  - Pivot Table (configurable pivot over selected columns)
- Use **Quick Actions** in the sidebar to refresh data (clears Streamlit cache and reruns).

## Caveats
- **Not implemented**: database/API sources, Excel export, clipboard copy, report generation, advanced search dialog (placeholders only).
- **Editable Grid** changes are not persisted beyond the current session rerun; the app states they are not persisted in this demo.
- SOP page requires `SOP.md` in the same directory; otherwise an error is shown.
- Date filtering assumes `df["Date"]` is datetime-like; sample data satisfies this. CSV uploads with non-datetime `Date` may break date-range behavior.
