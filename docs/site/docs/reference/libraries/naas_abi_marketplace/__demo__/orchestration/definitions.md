# definitions (Dagster orchestration demo)

## What it is
- A Dagster demo module that:
  - Defines one asset (`my_asset`) that writes RSS feed entries to disk as JSON.
  - Defines one asset job (`my_job`) that materializes `my_asset`.
  - Generates multiple sensors (one per Bing News RSS query) that trigger runs for each feed entry.
  - Exposes a Dagster `Definitions` object (`definitions`) wiring assets, job, and sensors.

## Public API
- `class MyAssetConfig(dagster.Config)`
  - Config schema for `my_asset`.
  - Fields:
    - `entry: Dict[str, Any]` — RSS entry object to persist.

- `@dagster.asset def my_asset(context: dagster.AssetExecutionContext, config: MyAssetConfig)`
  - Writes `config.entry` to a file under a demo data directory.
  - Output location:
    - `__demo__/orchestration/rss_feed/` (created if missing)
  - Filename format:
    - `YYYYMMDDTHHMMSS_<query>_<clean_title>.txt`
    - `<query>` is derived from the run tag `dagster/sensor_name` (expects `my_sensor_<query>`).
    - `<clean_title>` is the entry title sanitized by replacing spaces and `: / ?` with `_`.

- `my_job = dagster.define_asset_job("my_job", selection=[my_asset])`
  - Job that runs the single asset `my_asset`.

- `def get_rss_feed_content(url: str)`
  - Fetches and parses an RSS feed URL using `feedparser.parse`.
  - Returns the parsed feed object.

- `sensors: list`
  - A list of dynamically created Dagster sensors, one per hardcoded Bing News RSS URL.
  - Each sensor:
    - Is named `my_sensor_<query>`.
    - Runs every 30 seconds (`minimum_interval_seconds=30`).
    - Is enabled by default (`DefaultSensorStatus.RUNNING`).
    - Emits a `RunRequest` per RSS entry with:
      - `run_key=entry.title`
      - `run_config={"ops": {"my_asset": {"config": {"entry": entry}}}}`

- `definitions = dagster.Definitions(jobs=[my_job], sensors=sensors, assets=[my_asset])`
  - The module-level Dagster entrypoint bundling assets, job, and sensors.

## Configuration/Dependencies
- Python packages:
  - `dagster`
  - `feedparser` (imported inside `get_rss_feed_content`)
  - `naas_abi_core` (imported inside `my_asset`: `naas_abi_core.utils.Storage.ensure_data_directory`)
- Filesystem:
  - Creates directories and writes files under the directory returned by:
    - `ensure_data_directory("__demo__", "orchestration")`

## Usage
Minimal example to load the module’s Dagster `Definitions`:

```python
from naas_abi_marketplace.__demo__.orchestration.definitions import definitions

# Hand `definitions` to Dagster (e.g., via dagster dev / deployment configuration).
```

If you want to materialize the asset directly (without sensors), run the job from Dagster tooling using the loaded `definitions` and provide a config matching `MyAssetConfig.entry`.

## Caveats
- `my_asset` assumes `config.entry["published"]` matches the format `"%a, %d %b %Y %H:%M:%S %Z"`; mismatches will raise a `ValueError`.
- Sensors emit one run per RSS entry and use `entry.title` as `run_key`; duplicate titles may deduplicate/skip runs depending on Dagster run key behavior.
- The sensor query term used in filenames depends on the run tag `dagster/sensor_name`; runs launched outside these sensors will default to `unknown`.
