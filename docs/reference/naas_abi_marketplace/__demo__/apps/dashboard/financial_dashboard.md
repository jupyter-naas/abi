# financial_dashboard

## What it is
- A Streamlit-based **Financial Dashboard** demo app for multiple finance roles (Treasurer, Financial Controller, Accountant, CFO).
- Provides role-gated sections for:
  - Cash flow analysis
  - Budget vs actual
  - Project financial tracking
  - Account reconciliation status
- Includes a sidebar SOP viewer that loads `SOP.md` from the same directory.

## Public API
This module is an interactive Streamlit script (no public classes). Public callable defined:

- `load_financial_data() -> tuple[pd.DataFrame, pd.DataFrame]`
  - Loads (generates) sample financial datasets:
    - `cash_data`: daily cash series for Operating/Investing/Financing cash (cumulative random walks).
    - `pnl_data`: month-end P&L series for Revenue/COGS/Operating_Expenses/EBITDA.
  - Decorated with `@st.cache_data` to cache results within Streamlit.

## Configuration/Dependencies
- **Runtime**: Streamlit app.
- **Python packages**:
  - `streamlit`
  - `pandas`
  - `numpy`
  - `plotly.express`
  - `plotly.graph_objects`
- **Streamlit page config**:
  - `st.set_page_config(page_title="Financial Dashboard", page_icon="📊", layout="wide")`
- **Role permissions** (sidebar selection):
  - Treasurer: `cash_flow`, `investments`, `banking`, `liquidity`
  - Financial Controller: `budgets`, `forecasts`, `variance`, `projects`
  - Accountant: `transactions`, `reconciliation`, `journal_entries`, `compliance`
  - CFO: `all` (expanded to all modules listed in code)
- **SOP file**:
  - Reads `SOP.md` from `os.path.dirname(__file__)`.
  - If missing, shows a Streamlit error.
- **Port setting (only when executed as `__main__`)**:
  - Sets `os.environ["STREAMLIT_SERVER_PORT"] = "8502"`.

## Usage
Run as a Streamlit app:

```bash
streamlit run libs/naas-abi-marketplace/naas_abi_marketplace/__demo__/apps/dashboard/financial_dashboard.py
```

Within the app:
- Use the sidebar to select a **Role** to enable/disable dashboard sections.
- Click **📖 View SOP** to load and display `SOP.md`.

## Caveats
- Data is **mock/generated** using random values; metrics and charts are not connected to real financial systems.
- The `time_period` sidebar selector is present but **not used** to filter data in this script.
- The port environment variable is set inside `if __name__ == "__main__":` (Streamlit typically executes scripts in a way where this may not take effect as expected).
