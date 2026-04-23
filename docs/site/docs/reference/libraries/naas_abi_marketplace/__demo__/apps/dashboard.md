# ABI Interface Dashboard (`dashboard.py`)

## What it is
- A Streamlit app that acts as a central hub to list multiple local Streamlit-based interfaces.
- Shows each interface’s description, features, port, a direct link, and a simple online/offline status check.
- Provides basic system metrics and a few “quick action” buttons.

## Public API
- `check_interface_status(port)`
  - Sends an HTTP GET to `http://localhost:{port}` (2s timeout) and returns a status label:
    - `"🟢 Online"` if HTTP 200
    - `"🟡 Issues"` for non-200 responses
    - `"🔴 Offline"` on exceptions (connection errors, timeouts, etc.)

> Note: The rest of the file is Streamlit top-level app code (executed on import/run), not a reusable library API.

## Configuration/Dependencies
- **Dependencies**
  - `streamlit`
  - `requests`
  - Standard library: `datetime`
- **Runtime expectations**
  - The dashboard checks interface availability on `localhost` for the configured ports (`8501`–`8510`).
  - Uses Streamlit page configuration:
    - title: `"ABI Interface Dashboard"`
    - icon: `"🎛️"`
    - layout: `"wide"`

## Usage
Run the dashboard with Streamlit:

```bash
streamlit run libs/naas-abi-marketplace/naas_abi_marketplace/__demo__/apps/dashboard.py
```

Then open the displayed URL (typically `http://localhost:8501` unless Streamlit selects a different port).

## Caveats
- Status checking performs HTTP requests during rendering; it may be slow or repeatedly executed due to Streamlit reruns.
- The “Launch” button only writes text indicating the URL; it does not automatically open a browser window.
- “Quick Actions” buttons mostly display placeholder text (except “Refresh Status”, which calls `st.rerun()`).
