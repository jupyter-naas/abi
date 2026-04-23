# account_reconciliation

## What it is
A Streamlit dashboard for **account reconciliation and variance analysis**. It renders:
- Summary reconciliation metrics (variance, reconciled/pending/discrepancy counts)
- Account variance charts and priority list
- Styled detail tables (accounts + outstanding items with aging)
- Action buttons (UI-only notifications)
- A simple page route to display an `SOP.md` file from the same directory

## Public API
This module is primarily a Streamlit app (side-effectful at import/run). Public callables defined:

- `load_reconciliation_data() -> tuple[dict, pandas.DataFrame]`
  - Returns sample in-memory data:
    - `accounts` dict with book/bank balances, variance, and status
    - `outstanding_items` DataFrame with date, description, amount, type, days outstanding
  - Decorated with `@st.cache_data` for Streamlit caching.

- `style_variance(val) -> str`
  - Returns a CSS background-color based on variance magnitude.

- `style_status(val) -> str`
  - Returns a CSS background-color based on account status.

- `color_age(val) -> str`
  - Returns a CSS text color based on `Days_Outstanding` thresholds.

## Configuration/Dependencies
- **Runtime**: Streamlit app script.
- **Dependencies**:
  - `streamlit`
  - `pandas`
  - `plotly.express`
  - Python stdlib: `datetime`
- **Streamlit page config**: `page_title="Account Reconciliation"`, `layout="wide"`.
- **Port configuration**:
  - If executed as `__main__`, sets `os.environ["STREAMLIT_SERVER_PORT"] = "8501"`.
- **Optional file dependency**:
  - `SOP.md` in the same directory as this script (used when the “View SOP” sidebar button is clicked).

## Usage
Run with Streamlit:

```bash
streamlit run libs/naas-abi-marketplace/naas_abi_marketplace/__demo__/apps/reconciliation/account_reconciliation.py
```

Optional: ensure an SOP file exists alongside the script:

```text
.../reconciliation/
  account_reconciliation.py
  SOP.md
```

## Caveats
- This is a **UI demo** using **hard-coded sample data**; the action buttons only display Streamlit notifications (no real matching/reporting/reconciliation logic).
- Importing the module will execute Streamlit UI code immediately (not designed as a reusable library module).
- The “Custom Range” date input is collected but not used to filter any data in the current implementation.
- If `SOP.md` is missing, the SOP page displays an error message.
