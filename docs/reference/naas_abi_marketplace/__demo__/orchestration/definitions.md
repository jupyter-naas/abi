# definitions

## What it is
- A Dagster orchestration demo module that:
  - Defines a single asset (`my_asset`) that persists RSS feed entries to disk as JSON.
  - Defines an asset job (`my_job`) to materialize that asset.
  - Creates multiple sensors (one per hardcoded Bing News RSS query) that trigger runs for each RSS entry.
  - Exposes a Dagster `Definitions` object (`definitions`) wiring assets, job, and sensors together.

## Public API
- `class MyAssetConfig(dagster.Config)`
  - Asset config schema.
  - Field:
    - `entry: Dict[str, Any]` — an RSS entry object to write to disk.

- `@dagster.asset def my_asset(context: dagster.AssetExecutionContext, config: MyAssetConfig)`
  - Writes `config.entry` as pretty-printed JSON to a file under a demo data directory.
  - Directory layout:
    - `<data_dir>/rss_feed/` where `data_dir = ensure_data_directory("__demo__", "orchestration")`
  - Filename format:
    - `YYYYMMDDTHHMMSS_<query_term>_<clean_title>.txt`
    - `query_term` is derived from run tag `dagster/sensor_name` (expects `my_sensor_<query>`), otherwise `unknown`.
    - `clean_title` replaces spaces and `: / ?` with `_`.

- `my_job = dagster.define_asset_job("my_job", selection=[my_asset])`
  - Job that materializes `my_asset`.

- `def get_rss_feed_content(url: str)`
  - Fetches/parses the RSS feed from `url` using `feedparser.parse`.
  - Returns the parsed feed object.

- `sensors: list`
  - List of dynamically created Dagster sensors, one per hardcoded Bing News RSS URL.
  - Each sensor:
    - Name: `my_sensor_<query>` (query extracted from the URL after `q=`; `+` becomes `_`)
    - `default_status=dagster.DefaultSensorStatus.RUNNING`
    - `minimum_interval_seconds=30`
    - Emits a `dagster.RunRequest` per feed entry:
      - `run_key=entry.title`
      - `run_config={"ops": {"my_asset": {"config": {"entry": entry}}}}`

- `definitions = dagster.Definitions(jobs=[my_job], sensors=sensors, assets=[my_asset])`
  - Module entrypoint for Dagster.

## Configuration/Dependencies
- Dependencies:
  - `dagster`
  - `feedparser` (imported inside `get_rss_feed_content`)
  - `naas_abi_core.utils.Storage.ensure_data_directory` (imported inside `my_asset`)
- Filesystem:
  - Creates and writes to `<ensure_data_directory("__demo__", "orchestration")>/rss_feed/`.

## Usage
Load the Dagster definitions:

```python
from naas_abi_marketplace.__demo__.orchestration.definitions import definitions
```

## Caveats
- `my_asset` parses `config.entry["published"]` using `"%a, %d %b %Y %H:%M:%S %Z"`; mismatches raise `ValueError`.
- Sensors use `entry.title` as `run_key`; duplicate titles may deduplicate runs depending on Dagster behavior.
- If a run is not launched by these sensors (or lacks `dagster/sensor_name` tag), the filename’s `query_term` becomes `unknown`.
