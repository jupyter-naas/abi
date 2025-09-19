import dagster
import os
import json
import yaml
from typing import Dict, Any, List

class MyAssetConfig(dagster.Config):  # type: ignore
    entry: Dict[str, Any]

@dagster.asset
def raw_rss_asset(context: dagster.AssetExecutionContext, config: MyAssetConfig):
    """Save raw RSS feed XML exactly as it comes from the source URL for audit trail."""
    from abi.utils.Storage import ensure_data_directory
    from datetime import datetime
    import requests
    import hashlib
    
    # Create data directories following Code-Data Symmetry
    data_dir = ensure_data_directory("abi", "orchestration")
    raw_xml_dir = os.path.join(data_dir, "raw_rss_xml")
    os.makedirs(raw_xml_dir, exist_ok=True)
    
    # Use CURRENT timestamp
    current_timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    
    # Extract query term from context (sensor name contains query)
    sensor_name = context.run.tags.get("dagster/sensor_name", "unknown")
    query_term = sensor_name.replace("my_sensor_", "") if sensor_name.startswith("my_sensor_") else "unknown"
    
    # Get the RSS entry (this comes from feedparser, but we need the original XML)
    rss_entry = config.entry
    article_url = rss_entry.get("link", f"no_link_{current_timestamp}")
    article_id = hashlib.md5(article_url.encode()).hexdigest()[:12]
    
    # Get the original RSS feed URL from settings
    settings = get_settings()
    base_url = settings.get("base_url", "https://www.bing.com/news/search?format=RSS&q=")
    feed_url = f"{base_url}{query_term.replace('_', '+')}"
    
    context.log.info(f"🌐 Fetching raw RSS XML from: {feed_url}")
    
    try:
        # Fetch the raw RSS XML from the source
        response = requests.get(feed_url, timeout=30)
        response.raise_for_status()
        
        raw_xml_content = response.text
        
        # Save the raw XML exactly as received from the feed
        xml_filename = f"{current_timestamp}_{article_id}_{query_term}_raw_feed.xml"
        xml_file_path = os.path.join(raw_xml_dir, xml_filename)
        
        with open(xml_file_path, "w", encoding="utf-8") as f:
            f.write(raw_xml_content)
        
        context.log.info(f"💾 Saved raw RSS XML: {xml_filename}")
        
        # Also save metadata about this specific article for processing
        import json
        metadata = {
            "collection_metadata": {
                "collection_timestamp": current_timestamp,
                "query_term": query_term,
                "sensor_name": sensor_name,
                "collection_id": f"collection_{current_timestamp}_{article_id}",
                "article_id": article_id,
                "feed_url": feed_url,
                "xml_file": xml_filename
            },
            "article_info": {
                "title": rss_entry.get("title", "No title"),
                "link": article_url,
                "published": rss_entry.get("published", "unknown"),
                "summary": rss_entry.get("summary", "")
            }
        }
        
        # Save metadata for processing
        metadata_filename = f"{current_timestamp}_{article_id}_{query_term}_metadata.json"
        metadata_file_path = os.path.join(raw_xml_dir, metadata_filename)
        
        with open(metadata_file_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False, default=str)
        
        return {
            "raw_xml_file": xml_file_path,
            "metadata_file": metadata_file_path,
            "article_id": article_id,
            "collection_timestamp": current_timestamp,
            "query_term": query_term,
            "article_title": rss_entry.get("title", "No title")
        }
        
    except Exception as e:
        context.log.error(f"❌ Failed to fetch raw RSS XML: {e}")
        raise e


@dagster.asset
def bfo_ttl_asset(context: dagster.AssetExecutionContext, raw_rss_asset):
    """Process raw RSS XML through BFO pipeline and generate individual TTL files."""
    from abi.utils.Storage import ensure_data_directory
    import json
    import xml.etree.ElementTree as ET
    from pathlib import Path
    
    # Create TTL output directory
    data_dir = ensure_data_directory("abi", "orchestration")
    ttl_dir = os.path.join(data_dir, "bfo_ttl")
    os.makedirs(ttl_dir, exist_ok=True)
    
    # Get info from upstream asset
    raw_xml_file = raw_rss_asset["raw_xml_file"]
    metadata_file = raw_rss_asset["metadata_file"]
    article_id = raw_rss_asset["article_id"]
    collection_timestamp = raw_rss_asset["collection_timestamp"]
    query_term = raw_rss_asset["query_term"]
    article_title = raw_rss_asset["article_title"]
    
    context.log.info(f"🔄 Processing raw XML for article: {article_title}")
    
    # Load metadata
    with open(metadata_file, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
    
    # Read raw XML content
    with open(raw_xml_file, 'r', encoding='utf-8') as f:
        raw_xml_content = f.read()
    
    try:
        # Parse the raw RSS XML to extract the specific article
        root = ET.fromstring(raw_xml_content)
        
        # Find the specific article in the RSS feed by title match
        article_found = False
        rss_entry_data = None
        
        # Look for the article in RSS format
        for item in root.findall(".//item"):
            title_elem = item.find("title")
            if title_elem is not None and title_elem.text == article_title:
                # Extract RSS entry data from raw XML
                rss_entry_data = {}
                for child in item:
                    if child.tag == "link":
                        rss_entry_data["link"] = child.text
                    elif child.tag == "title":
                        rss_entry_data["title"] = child.text
                    elif child.tag == "description":
                        rss_entry_data["summary"] = child.text
                    elif child.tag == "pubDate":
                        rss_entry_data["published"] = child.text
                    elif child.tag == "guid":
                        rss_entry_data["guid"] = child.text
                    # Add more fields as needed
                article_found = True
                break
        
        if not article_found:
            context.log.warning(f"⚠️ Article '{article_title}' not found in raw XML, using metadata")
            rss_entry_data = metadata["article_info"]
        
        # Import BFO pipeline components
        from src.core.abi.pipelines.RSSFeedToBFOPipeline import (
            RSSFeedToBFOPipeline,
            RSSFeedToBFOPipelineConfiguration,
            RSSFeedToBFOPipelineParameters
        )
        
        # Mock triple store for TTL generation
        class TTLGeneratorStore:
            def __init__(self):
                self.generated_graph = None
                
            def insert(self, graph):
                self.generated_graph = graph
                return True
        
        # Initialize BFO pipeline
        ttl_store = TTLGeneratorStore()
        config = RSSFeedToBFOPipelineConfiguration(triple_store=ttl_store)
        pipeline = RSSFeedToBFOPipeline(config)
        
        # Create pipeline parameters from raw XML data
        rss_data = {
            "collection_timestamp": metadata["collection_metadata"]["collection_timestamp"],
            "query_term": metadata["collection_metadata"]["query_term"],
            "sensor_name": metadata["collection_metadata"]["sensor_name"],
            "rss_entry": rss_entry_data,
            "raw_xml_source": raw_xml_file  # Reference to original source
        }
        
        parameters = RSSFeedToBFOPipelineParameters(
            rss_data=rss_data,
            collection_id=metadata["collection_metadata"]["collection_id"]
        )
        
        # Generate BFO RDF graph
        result_graph = pipeline.run(parameters)
        
        # Generate individual TTL file for this article instance
        ttl_filename = f"{collection_timestamp}_{article_id}_{query_term}_bfo.ttl"
        ttl_file_path = os.path.join(ttl_dir, ttl_filename)
        
        # Serialize graph to TTL format
        ttl_content = result_graph.serialize(format='turtle')
        
        with open(ttl_file_path, 'w', encoding='utf-8') as f:
            f.write(ttl_content)
            
        context.log.info(f"📄 Generated TTL file: {ttl_filename} ({len(result_graph)} triples)")
        
        return {
            "ttl_file_path": ttl_file_path,
            "article_id": article_id,
            "triples_count": len(result_graph),
            "ttl_filename": ttl_filename,
            "article_title": article_title
        }
        
    except Exception as e:
        context.log.error(f"❌ Error processing raw XML through BFO pipeline: {e}")
        raise e

@dagster.asset
def oxigraph_insert_asset(context: dagster.AssetExecutionContext, bfo_ttl_asset):
    """Send TTL files to Oxigraph triple store."""
    import requests
    from pathlib import Path
    
    ttl_file_path = bfo_ttl_asset["ttl_file_path"]
    article_id = bfo_ttl_asset["article_id"]
    triples_count = bfo_ttl_asset["triples_count"]
    ttl_filename = bfo_ttl_asset["ttl_filename"]
    
    context.log.info(f"📤 Sending TTL file to Oxigraph: {ttl_filename}")
    
    try:
        # Read TTL content
        with open(ttl_file_path, 'r', encoding='utf-8') as f:
            ttl_content = f.read()
        
        # Oxigraph endpoint (through proxy)
        oxigraph_url = "http://localhost:7878/store"
        
        # Send TTL data to Oxigraph
        headers = {
            'Content-Type': 'application/x-turtle'
        }
        
        response = requests.post(
            f"{oxigraph_url}?graph={article_id}",  # Use article ID as named graph
            data=ttl_content,
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 204:  # Oxigraph returns 204 for successful insertions
            context.log.info(f"✅ Successfully inserted {triples_count} triples into Oxigraph for article {article_id}")
            return {
                "status": "success",
                "article_id": article_id,
                "triples_inserted": triples_count,
                "graph_name": article_id,
                "ttl_file": ttl_filename
            }
        else:
            context.log.error(f"❌ Failed to insert into Oxigraph. Status: {response.status_code}, Response: {response.text}")
            return {
                "status": "error",
                "article_id": article_id,
                "error": f"HTTP {response.status_code}: {response.text}"
            }
            
    except Exception as e:
        context.log.error(f"❌ Error sending TTL to Oxigraph: {e}")
        return {
            "status": "error", 
            "article_id": article_id,
            "error": str(e)
        }

# Update job to include all three assets in pipeline
my_job = dagster.define_asset_job("my_job", selection=[raw_rss_asset, bfo_ttl_asset, oxigraph_insert_asset])

def get_rss_feed_content(url: str):
    import feedparser
    
    feed = feedparser.parse(url)
    return feed


def load_topics_config() -> Dict[str, Any]:
    """Load monitoring topics from YAML configuration file."""
    config_path = os.path.join(os.path.dirname(__file__), "topics.yaml")
    
    try:
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
            return config
    except FileNotFoundError:
        raise FileNotFoundError(f"Topics configuration file not found: {config_path}")
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in topics configuration: {e}")

def get_all_targets() -> List[str]:
    """Get all monitoring targets from configuration."""
    config = load_topics_config()
    monitoring_topics = config.get("monitoring_topics", {})
    
    all_targets = []
    for category, topics in monitoring_topics.items():
        if isinstance(topics, list):
            all_targets.extend(topics)
    
    return all_targets

def get_settings() -> Dict[str, Any]:
    """Get configuration settings."""
    config = load_topics_config()
    return config.get("settings", {})

# Load configuration
all_targets = get_all_targets()
settings = get_settings()

sensors = []
base_url = settings.get("base_url", "https://www.bing.com/news/search?format=RSS&q=")
polling_interval = settings.get("polling_interval_seconds", 30)

for target in all_targets:
    url = f"{base_url}{target}"
    query = target.replace("+", "_").replace(" ", "_")
    
    sensor = dagster.sensor(name=f"my_sensor_{query}",
                            job=my_job,
                            default_status=dagster.DefaultSensorStatus.RUNNING,
                            minimum_interval_seconds=polling_interval)
    def inner_sensor(url):
        
        def my_sensor():
            feed = get_rss_feed_content(url)
            for entry in feed.entries:
                yield dagster.RunRequest(run_key=entry.title, run_config={"ops": {"raw_rss_asset": {"config": {"entry": entry}}}})
                
        return my_sensor
            
    
    sensors.append(sensor(inner_sensor(url)))


# Production assets, jobs, and sensors
all_assets = [raw_rss_asset, bfo_ttl_asset, oxigraph_insert_asset]
all_jobs = [my_job]
all_sensors = sensors

definitions = dagster.Definitions(
    jobs=all_jobs, 
    sensors=all_sensors, 
    assets=all_assets
)