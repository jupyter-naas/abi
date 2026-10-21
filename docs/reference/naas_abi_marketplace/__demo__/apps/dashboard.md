# ABI Interface Dashboard (`dashboard.py`)

## What it is
- A Streamlit dashboard that lists multiple local Streamlit interfaces (by category) with:
  - Name, description, features, port, and a direct link
  - A simple online/offline/issue status check via HTTP
- Displays basic counts (total interfaces, online interfaces, categories) and a few quick-action buttons.

## Public API
- `check_interface_status(port)`
  - Purpose: Check whether a local interface is reachable on `http://localhost:{port}`.
  - Behavior:
    - Performs `GET` with `timeout=2`
    - Returns:
      - `"🟢 Online"` if HTTP 200
      - `"🟡 Issues"` if reachable but non-200
      - `"🔴 Offline"` on any exception

> All other logic is Streamlit top-level app code executed when the file is run.

## Configuration/Dependencies
- Dependencies:
  - `streamlit`
  - `requests`
  - Standard library: `datetime`
- Streamlit page config:
  - `page_title="ABI Interface Dashboard"`
  - `page_icon="🎛️"`
  - `layout="wide"`
- Runtime expectations:
  - Checks interfaces on `localhost` ports `8501`–`8510` (as defined in `interfaces`).

## Usage
Run with Streamlit:

```bash
streamlit run libs/naas-abi-marketplace/naas_abi_marketplace/__demo__/apps/dashboard.py
```

## Caveats
- Status checks (`requests.get`) run during rendering and may repeat on Streamlit reruns.
- The “Launch” button only writes an “Opening http://...” message; it does not open a browser window.
- “View All Tables” and “Open All Chat” buttons only display placeholder text; they do not perform navigation or launching actions.
