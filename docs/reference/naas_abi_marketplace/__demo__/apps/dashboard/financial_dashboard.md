# financial_dashboard

## What it is
- A Streamlit demo **Financial Dashboard** for multiple finance roles:
  - Treasurer
  - Financial Controller
  - Accountant
  - CFO
- Provides role-gated sections for:
  - Cash flow analysis (Plotly charts)
  - Budget vs actual (mock data + variance charts)
  - Project financial tracking (mock data + utilization/status)
  - Account reconciliation status (mock data + quick actions)
- Includes a sidebar SOP viewer that loads `SOP.md` from the same directory.

## Public API
This file is primarily an interactive Streamlit script (no public classes). Public callable:

- `load_financial_data() -> tuple[pandas.DataFrame, pandas.DataFrame]`
  - Generates sample datasets and returns:
    - `cash_data`: daily cumulative series for `Operating_Cash`, `Investing_Cash`, `Financing_Cash`
    - `pnl_data`: month-end series for `Revenue`, `COGS`, `Operating_Expenses`, and computed `EBITDA`
  - Decorated with `@st.cache_data` (cached within Streamlit).

## Configuration/Dependencies
- **Runtime**: Streamlit
- **Dependencies**:
  - `streamlit`
  - `pandas`
  - `numpy`
  - `plotly.express`
  - `plotly.graph_objects`
- **Streamlit page config**:
  - `st.set_page_config(page_title="Financial Dashboard", page_icon="📊", layout="wide")`
- **Role-based permissions** (sidebar selector):
  - Treasurer: `cash_flow`, `investments`, `banking`, `liquidity`
  - Financial Controller: `budgets`, `forecasts`, `variance`, `projects`
  - Accountant: `transactions`, `reconciliation`, `journal_entries`, `compliance`
  - CFO: `all` (expanded to all modules listed in code)
- **SOP file**:
  - Loaded from `SOP.md` in the same directory as this script (`os.path.dirname(__file__)`)
  - Displays Streamlit error if missing/unreadable
- **Port setting**:
  - When executed as `__main__`, sets `os.environ["STREAMLIT_SERVER_PORT"] = "8502"`.

## Usage
Run with Streamlit:

```bash
streamlit run libs/naas-abi-marketplace/naas_abi_marketplace/__demo__/apps/dashboard/financial_dashboard.py
```

In the app:
- Select a **Role** in the sidebar to enable/disable dashboard sections.
- Click **📖 View SOP** to open the SOP page (renders `SOP.md`).

## Caveats
- All financial data is **randomly generated/mock**; it is not connected to external systems.
- The sidebar **Time Period** selector is present but **not used** to filter the displayed datasets.
- The `STREAMLIT_SERVER_PORT` environment variable is set only under `if __name__ == "__main__":`; depending on how Streamlit runs the script, this may not reliably control the port.
