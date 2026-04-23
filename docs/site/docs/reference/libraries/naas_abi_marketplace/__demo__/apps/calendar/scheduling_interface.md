# Scheduling & Calendar Interface (`scheduling_interface.py`)

## What it is
- A Streamlit app that renders a multi-role scheduling dashboard with:
  - Calendar views (week/month/day/agenda)
  - Basic metrics (today/this week/high priority/conflicts)
  - Mock resource availability (rooms, equipment)
  - Quick action buttons (mocked)
  - Simple analytics charts (Plotly)

## Public API
This module is a Streamlit script (UI-first) with one reusable function:

- `load_calendar_data() -> pandas.DataFrame`
  - Generates a mock events dataset (50 events across the next ~30 days).
  - Cached via `@st.cache_data`.
  - Output columns: `Title`, `Type`, `Date` (datetime), `Start_Time` (HH:00), `Duration` (minutes), `Attendees`, `Location`, `Priority`, `Status`.

There are no public classes.

## Configuration/Dependencies
- **Runtime**: Streamlit script; intended to be launched with `streamlit run`.
- **Sets Streamlit page config**:
  - `page_title="Scheduling Center"`, `page_icon="📅"`, `layout="wide"`.
- **Environment** (only when executed as `__main__`):
  - Sets `STREAMLIT_SERVER_PORT=8504` (note: Streamlit CLI may still control the port depending on how it’s launched).
- **Dependencies**:
  - `streamlit`, `pandas`, `plotly.express`, `numpy`
  - Standard library: `datetime`, `calendar`, `os` (only on SOP page / main guard)

## Usage
Run the app:

```bash
streamlit run libs/naas-abi-marketplace/naas_abi_marketplace/__demo__/apps/calendar/scheduling_interface.py
```

Minimal example of using the only reusable function (outside Streamlit context):

```python
from naas_abi_marketplace.__demo__.apps.calendar.scheduling_interface import load_calendar_data

df = load_calendar_data()
print(df.head())
```

## Caveats
- Data is **mocked/random** (`numpy.random`), including event generation and resource availability; results change across runs.
- The “Schedule Conflicts” metric is also mocked (`np.random.randint(0, 3)`).
- SOP view expects a `SOP.md` file in the same directory; if missing, the UI shows an error.
- The weekly-load bar chart uses `groupby(dayofweek).size()` and plots `weekly_load.values` against fixed day labels; missing weekdays in the data can lead to a mismatch between labels and counts.
