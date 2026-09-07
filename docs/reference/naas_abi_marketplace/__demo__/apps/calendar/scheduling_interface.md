# Scheduling & Calendar Interface (`scheduling_interface.py`)

## What it is
- A Streamlit dashboard for scheduling and calendar management across multiple roles (e.g., Project Manager, HR, Sales).
- Renders multiple calendar views (Week/Month/Day/Agenda), summary metrics, resource availability, quick actions, and basic analytics charts.
- Uses randomly generated (mock) event and availability data.

## Public API
This module is primarily a Streamlit script. The only reusable function is:

- `load_calendar_data() -> pandas.DataFrame`
  - Generates a mock dataset of 50 events over the next 30 days.
  - Cached with `@st.cache_data`.
  - Returns a DataFrame with columns:
    - `Title`, `Type`, `Date` (`datetime`), `Start_Time` (`"HH:00"`), `Duration` (minutes),
      `Attendees`, `Location`, `Priority`, `Status`.

No public classes are defined.

## Configuration/Dependencies
- **Runs as a Streamlit app**: intended to be started via `streamlit run ...`.
- **Streamlit page config**: `page_title="Scheduling Center"`, `page_icon="📅"`, `layout="wide"`.
- **Environment variable (only under `__main__`)**:
  - Sets `STREAMLIT_SERVER_PORT=8504`.
- **Dependencies**:
  - `streamlit`, `pandas`, `plotly.express`, `numpy`
  - Standard library: `datetime`, `timedelta`, `calendar`, `os` (used in `__main__` and SOP loader)

## Usage
Run the app:
```bash
streamlit run libs/naas-abi-marketplace/naas_abi_marketplace/__demo__/apps/calendar/scheduling_interface.py
```

Use the data generator function directly:
```python
from naas_abi_marketplace.__demo__.apps.calendar.scheduling_interface import load_calendar_data

df = load_calendar_data()
print(df[["Title", "Type", "Date"]].head())
```

## Caveats
- All events, conflicts, and resource availability are **randomly generated** via `numpy.random`; outputs vary between runs.
- The SOP page attempts to load `SOP.md` from the same directory; if missing, the UI displays an error.
- The weekly-load bar chart uses fixed day labels (`Mon`..`Sun`) but plots `weekly_load.values`; if some weekdays are absent in the data, label/value alignment may not reflect missing days.
