import dagster
import os
import json
from typing import Dict, Any

class MyAssetConfig(dagster.Config):  # type: ignore
    entry: Dict[str, Any]

@dagster.asset
def my_asset(context: dagster.AssetExecutionContext, config: MyAssetConfig):
    from abi.utils.Storage import ensure_data_directory
    
    # Create data directory following Code-Data Symmetry
    data_dir = ensure_data_directory("__demo__", "orchestration")
    rss_dir = os.path.join(data_dir, "rss_feed")
    os.makedirs(rss_dir, exist_ok=True)
    
    # Extract query term from context (sensor name contains query)
    sensor_name = context.run.tags.get("dagster/sensor_name", "unknown")
    query_term = sensor_name.replace("my_sensor_", "") if sensor_name.startswith("my_sensor_") else "unknown"
    
    # Clean title for filename
    clean_title = config.entry["title"].replace(" ", "_").replace(":", "_").replace("/", "_").replace("?", "_")
    
    # Create timestamp in ISO 8601 compact format (YYYYMMDDTHHMMSS)
    from datetime import datetime
    timestamp = datetime.strptime(config.entry["published"], "%a, %d %b %Y %H:%M:%S %Z").strftime("%Y%m%dT%H%M%S")
    
    # Build filename: TIMESTAMP_QUERY_TITLE.txt
    filename = f"{timestamp}_{query_term}_{clean_title}.txt"
    
    with open(os.path.join(rss_dir, filename), "w") as f:
        f.write(json.dumps(config.entry, indent=4))


my_job = dagster.define_asset_job("my_job", selection=[my_asset])

def get_rss_feed_content(url: str):
    import feedparser
    
    feed = feedparser.parse(url)
    return feed


sensors = []
for url in [
    "https://www.bing.com/news/search?format=RSS&q=Ontology",
    "https://www.bing.com/news/search?format=RSS&q=AI",
    "https://www.bing.com/news/search?format=RSS&q=Palantir",
    "https://www.bing.com/news/search?format=RSS&q=LLM",
    "https://www.bing.com/news/search?format=RSS&q=Elon+Musk",
    "https://www.bing.com/news/search?format=RSS&q=OpenAI",
    "https://www.bing.com/news/search?format=RSS&q=Google",
    "https://www.bing.com/news/search?format=RSS&q=Meta",
    "https://www.bing.com/news/search?format=RSS&q=Microsoft",
    "https://www.bing.com/news/search?format=RSS&q=Apple",
    "https://www.bing.com/news/search?format=RSS&q=Amazon",
    "https://www.bing.com/news/search?format=RSS&q=Tesla",
    "https://www.bing.com/news/search?format=RSS&q=SpaceX",
    "https://www.bing.com/news/search?format=RSS&q=NASA",
    "https://www.bing.com/news/search?format=RSS&q=Donald+Trump"]:
    query = url.split('q=')[1].replace("+", "_").replace(" ", "_")
    
    sensor = dagster.sensor(name=f"my_sensor_{query}",
                            job=my_job,
                            default_status=dagster.DefaultSensorStatus.RUNNING,
                            minimum_interval_seconds=30)
    def inner_sensor(url):
        
        def my_sensor():
            feed = get_rss_feed_content(url)
            for entry in feed.entries:
                yield dagster.RunRequest(run_key=entry.title, run_config={"ops": {"my_asset": {"config": {"entry": entry}}}})
                
        return my_sensor
            
    
    sensors.append(sensor(inner_sensor(url)))


definitions = dagster.Definitions(jobs=[my_job], sensors=sensors, assets=[my_asset])