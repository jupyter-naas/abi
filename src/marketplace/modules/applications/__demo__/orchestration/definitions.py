import dagster
import os
import json
from typing import Dict, Any, List
from datetime import datetime

class GlobalNewsConfig(dagster.Config):  # type: ignore[misc]
    """Configuration for global news intelligence collection"""
    entry: Dict[str, Any]
    country: str
    outlet_type: str

@dagster.asset
def global_news_asset(context: dagster.AssetExecutionContext, config: GlobalNewsConfig):
    """Collect and process global news from major outlets"""
    from abi.utils.Storage import ensure_data_directory
    
    # Create data directory following Code-Data Symmetry
    data_dir = ensure_data_directory("__demo__", "orchestration")
    
    # Create country and outlet-specific subdirectories
    news_dir = os.path.join(data_dir, "global_news", config.country, config.outlet_type)
    os.makedirs(news_dir, exist_ok=True)
    
    # Extract source information from sensor context
    sensor_name = context.run.tags.get("dagster/sensor_name", "unknown")
    outlet_name = sensor_name.replace("news_", "") if sensor_name.startswith("news_") else "unknown"
    
    # Clean title for filename
    title = config.entry.get("title", "untitled")
    clean_title = title.replace(" ", "_").replace(":", "_").replace("/", "_").replace("?", "_")[:100]
    
    # Create timestamp in ISO 8601 compact format
    published = config.entry.get("published", "")
    try:
        if published:
            timestamp = datetime.strptime(published, "%a, %d %b %Y %H:%M:%S %Z").strftime("%Y%m%dT%H%M%S")
        else:
            timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    except (ValueError, TypeError):
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    
    # Enhanced data structure with geopolitical metadata
    enhanced_entry = {
        "metadata": {
            "collected_at": datetime.now().isoformat(),
            "country": config.country,
            "outlet_type": config.outlet_type,
            "outlet_name": outlet_name,
            "intelligence_type": "global_news"
        },
        "content": config.entry
    }
    
    # Build filename: TIMESTAMP_OUTLET_TITLE.json
    filename = f"{timestamp}_{outlet_name}_{clean_title}.json"
    
    filepath = os.path.join(news_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(json.dumps(enhanced_entry, indent=4, ensure_ascii=False))
    
    context.log.info(f"Collected global news: {config.country}/{config.outlet_type}/{outlet_name} - {title}")
    return enhanced_entry

# Define the job
global_news_job = dagster.define_asset_job("global_news_job", selection=[global_news_asset])

def get_rss_feed_content(url: str) -> List[Dict[str, Any]]:
    """Fetch and parse RSS feed content"""
    import feedparser
    
    try:
        feed = feedparser.parse(url)
        return feed.entries if hasattr(feed, 'entries') else []
    except Exception as e:
        print(f"Error fetching RSS feed {url}: {e}")
        return []

# Strategic Global News Sources
GLOBAL_NEWS_SOURCES = {
    # United States - Major News Outlets
    "us": {
        "mainstream": {
            "CNN": "http://rss.cnn.com/rss/edition.rss",
            "BBC_US": "http://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml",
            "Reuters_US": "https://www.reutersagency.com/feed/?best-topics=political-general&post_type=best",
            "AP_News": "https://www.bing.com/news/search?format=RSS&q=site:apnews.com",
            "NPR": "https://www.bing.com/news/search?format=RSS&q=site:npr.org",
            "ABC_News": "https://www.bing.com/news/search?format=RSS&q=site:abcnews.go.com"
        },
        "business": {
            "Wall_Street_Journal": "https://www.bing.com/news/search?format=RSS&q=site:wsj.com",
            "Bloomberg": "https://www.bing.com/news/search?format=RSS&q=site:bloomberg.com",
            "CNBC": "https://www.bing.com/news/search?format=RSS&q=site:cnbc.com",
            "Forbes": "https://www.bing.com/news/search?format=RSS&q=site:forbes.com"
        },
        "tech": {
            "TechCrunch": "https://www.bing.com/news/search?format=RSS&q=site:techcrunch.com",
            "Wired": "https://www.bing.com/news/search?format=RSS&q=site:wired.com",
            "Ars_Technica": "https://www.bing.com/news/search?format=RSS&q=site:arstechnica.com"
        }
    },
    
    # France - Major News Outlets
    "france": {
        "mainstream": {
            "Le_Monde": "https://www.bing.com/news/search?format=RSS&q=site:lemonde.fr",
            "Le_Figaro": "https://www.bing.com/news/search?format=RSS&q=site:lefigaro.fr",
            "Liberation": "https://www.bing.com/news/search?format=RSS&q=site:liberation.fr",
            "France24": "https://www.bing.com/news/search?format=RSS&q=site:france24.com",
            "RFI": "https://www.bing.com/news/search?format=RSS&q=site:rfi.fr"
        },
        "business": {
            "Les_Echos": "https://www.bing.com/news/search?format=RSS&q=site:lesechos.fr",
            "La_Tribune": "https://www.bing.com/news/search?format=RSS&q=site:latribune.fr"
        },
        "tech": {
            "01net": "https://www.bing.com/news/search?format=RSS&q=site:01net.com",
            "Numerama": "https://www.bing.com/news/search?format=RSS&q=site:numerama.com"
        }
    },
    
    # United Kingdom - Major News Outlets
    "uk": {
        "mainstream": {
            "BBC": "http://feeds.bbci.co.uk/news/rss.xml",
            "The_Guardian": "https://www.bing.com/news/search?format=RSS&q=site:theguardian.com",
            "The_Telegraph": "https://www.bing.com/news/search?format=RSS&q=site:telegraph.co.uk",
            "The_Times": "https://www.bing.com/news/search?format=RSS&q=site:thetimes.co.uk",
            "Sky_News": "https://www.bing.com/news/search?format=RSS&q=site:news.sky.com"
        },
        "business": {
            "Financial_Times": "https://www.bing.com/news/search?format=RSS&q=site:ft.com",
            "Reuters_UK": "https://www.bing.com/news/search?format=RSS&q=site:reuters.com+UK"
        },
        "tech": {
            "The_Register": "https://www.bing.com/news/search?format=RSS&q=site:theregister.com"
        }
    }
}

# Generate sensors dynamically for all news sources
sensors = []

for country, outlet_types in GLOBAL_NEWS_SOURCES.items():
    for outlet_type, outlets in outlet_types.items():
        for outlet_name, url in outlets.items():
            sensor_name = f"news_{country}_{outlet_type}_{outlet_name.lower()}"
            
            sensor = dagster.sensor(
                name=sensor_name,
                job=global_news_job,
                default_status=dagster.DefaultSensorStatus.RUNNING,
                minimum_interval_seconds=900  # 15 minutes - reasonable for news
            )
            
            def create_sensor_function(url, country, outlet_type, outlet_name):
                def sensor_function():
                    """Monitor global news sources for new content"""
                    entries = get_rss_feed_content(url)
                    
                    # Process up to 10 most recent entries for news
                    for entry in entries[:10]:
                        if hasattr(entry, 'title') and hasattr(entry, 'published'):
                            yield dagster.RunRequest(
                                run_key=f"{country}_{outlet_type}_{outlet_name}_{entry.title}_{entry.published}",
                                run_config={
                                    "ops": {
                                        "global_news_asset": {
                                            "config": {
                                                "entry": dict(entry),
                                                "country": country,
                                                "outlet_type": outlet_type
                                            }
                                        }
                                    }
                                }
                            )
                
                return sensor_function
            
            sensors.append(sensor(create_sensor_function(url, country, outlet_type, outlet_name)))

# Export definitions
definitions = dagster.Definitions(
    jobs=[global_news_job], 
    sensors=sensors, 
    assets=[global_news_asset]
)
