# account_reconciliation

## What it is
A Streamlit dashboard script for **account reconciliation and variance analysis**. It displays:
- Sidebar controls (account type, reconciliation period, optional custom date range)
- Summary metrics (total variance, reconciled/pending/discrepancy counts)
- Variance visualizations (bar chart, priority list)
- Styled detail tables (accounts and outstanding items with aging)
- UI-only action buttons (show Streamlit notifications)
- A simple page route to display an `SOP.md` file from the same directory

## Public API
This module is a **Streamlit app** (executes UI code on import/run). Public callables defined:

- `load_reconciliation_data() -> tuple[dict, pandas.DataFrame]`
  - Returns in-memory sample data:
    - `accounts` dict with `book`, `bank`, `variance`, `status`
    - `outstanding_items` DataFrame with `Date`, `Description`, `Amount`, `Type`, `Days_Outstanding`
  - Decorated with `@st.cache_data`.

- `style_variance(val) -> str`
  - Returns a CSS `background-color` based on variance magnitude.

- `style_status(val) -> str`
  - Returns a CSS `background-color` based on account status.

- `color_age(val) -> str`
  - Returns a CSS text `color` based on `Days_Outstanding` thresholds.

## Configuration/Dependencies
- **Runtime**: Streamlit app script.
- **Dependencies**:
  - `streamlit`
  - `pandas`
  - `plotly.express`
  - stdlib: `datetime`
- **Streamlit page config**: `page_title="Account Reconciliation"`, `layout="wide"` (also sets `page_icon`).
- **Port configuration**:
  - When executed as `__main__`, sets `os.environ["STREAMLIT_SERVER_PORT"] = "8501"`.
- **Optional file dependency**:
  - `SOP.md` in the same directory as the script (displayed via the “View SOP” sidebar button).

## Usage
Run with Streamlit:

```bash
streamlit run libs/naas-abi-marketplace/naas_abi_marketplace/__demo__/apps/reconciliation/account_reconciliation.py
```

Optional SOP file layout:

```text
.../reconciliation/
  account_reconciliation.py
  SOP.md
```

## Caveats
- Uses **hard-coded sample data**; no real reconciliation, matching, or reporting is implemented.
- The sidebar “Custom Range” date input is collected but **not used** to filter data.
- Action buttons only trigger Streamlit messages (`success/info/warning`).
- Importing/running the module executes the Streamlit UI immediately (not a library-style module).
- If `SOP.md` is missing, the SOP page shows an error and the app continues to run.
