import dagster
import os
import json
from typing import Dict, Any, List
from datetime import datetime

class AIIntelligenceConfig(dagster.Config):  # type: ignore[misc]
    """Configuration for AI industry intelligence collection"""
    entry: Dict[str, Any]
    source_category: str

@dagster.asset
def ai_intelligence_asset(context: dagster.AssetExecutionContext, config: AIIntelligenceConfig):
    """Collect and process AI industry intelligence from RSS feeds"""
    from abi.utils.Storage import ensure_data_directory
    
    # Create data directory following Code-Data Symmetry
    data_dir = ensure_data_directory("abi", "orchestration")
    
    # Create category-specific subdirectories
    category_dir = os.path.join(data_dir, "ai_intelligence", config.source_category)
    os.makedirs(category_dir, exist_ok=True)
    
    # Extract source information from sensor context
    sensor_name = context.run.tags.get("dagster/sensor_name", "unknown")
    source_name = sensor_name.replace("ai_intel_", "") if sensor_name.startswith("ai_intel_") else "unknown"
    
    # Clean title for filename
    title = config.entry.get("title", "untitled")
    clean_title = title.replace(" ", "_").replace(":", "_").replace("/", "_").replace("?", "_")[:100]  # Limit length
    
    # Create timestamp in ISO 8601 compact format
    published = config.entry.get("published", "")
    try:
        if published:
            timestamp = datetime.strptime(published, "%a, %d %b %Y %H:%M:%S %Z").strftime("%Y%m%dT%H%M%S")
        else:
            timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    except (ValueError, TypeError):
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    
    # Build filename: TIMESTAMP_SOURCE_TITLE.json
    filename = f"{timestamp}_{source_name}_{clean_title}.json"
    
    # Enhanced data structure with metadata
    enhanced_entry = {
        "metadata": {
            "collected_at": datetime.now().isoformat(),
            "source_category": config.source_category,
            "source_name": source_name,
            "intelligence_type": "rss_feed"
        },
        "content": config.entry
    }
    
    filepath = os.path.join(category_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(json.dumps(enhanced_entry, indent=4, ensure_ascii=False))
    
    context.log.info(f"Collected AI intelligence: {config.source_category}/{source_name} - {title}")
    return enhanced_entry

# Define the job
ai_intelligence_job = dagster.define_asset_job("ai_intelligence_job", selection=[ai_intelligence_asset])

def get_rss_feed_content(url: str) -> List[Dict[str, Any]]:
    """Fetch and parse RSS feed content"""
    import feedparser
    
    try:
        feed = feedparser.parse(url)
        return feed.entries if hasattr(feed, 'entries') else []
    except Exception as e:
        print(f"Error fetching RSS feed {url}: {e}")
        return []

# Strategic AI Industry RSS Sources
AI_INTELLIGENCE_SOURCES = {
    # AI Labs & Companies
    "labs": {
        "OpenAI": "https://www.bing.com/news/search?format=RSS&q=OpenAI",
        "Anthropic": "https://www.bing.com/news/search?format=RSS&q=Anthropic+AI",
        "xAI": "https://www.bing.com/news/search?format=RSS&q=xAI+Elon+Musk",
        "Google_DeepMind": "https://www.bing.com/news/search?format=RSS&q=Google+DeepMind",
        "Meta_AI": "https://www.bing.com/news/search?format=RSS&q=Meta+AI+Facebook",
        "Mistral_AI": "https://www.bing.com/news/search?format=RSS&q=Mistral+AI",
        "Perplexity": "https://www.bing.com/news/search?format=RSS&q=Perplexity+AI",
        "DeepSeek": "https://www.bing.com/news/search?format=RSS&q=DeepSeek+AI",
        "Alibaba_Qwen": "https://www.bing.com/news/search?format=RSS&q=Alibaba+Qwen+AI",
        "Cohere": "https://www.bing.com/news/search?format=RSS&q=Cohere+AI",
        "Stability_AI": "https://www.bing.com/news/search?format=RSS&q=Stability+AI",
        "Hugging_Face": "https://www.bing.com/news/search?format=RSS&q=Hugging+Face+AI"
    },
    
    # Specific AI Models
    "models": {
        "GPT": "https://www.bing.com/news/search?format=RSS&q=GPT+model+AI",
        "Claude": "https://www.bing.com/news/search?format=RSS&q=Claude+AI+model",
        "Grok": "https://www.bing.com/news/search?format=RSS&q=Grok+AI+model",
        "Gemini": "https://www.bing.com/news/search?format=RSS&q=Gemini+AI+model",
        "Llama": "https://www.bing.com/news/search?format=RSS&q=Llama+AI+model",
        "Mistral": "https://www.bing.com/news/search?format=RSS&q=Mistral+AI+model",
        "Qwen": "https://www.bing.com/news/search?format=RSS&q=Qwen+AI+model"
    },
    
    # Research & Academic
    "research": {
        "AI_Research": "https://www.bing.com/news/search?format=RSS&q=artificial+intelligence+research",
        "Machine_Learning": "https://www.bing.com/news/search?format=RSS&q=machine+learning+research",
        "LLM_Research": "https://www.bing.com/news/search?format=RSS&q=large+language+model+research",
        "AGI_Research": "https://www.bing.com/news/search?format=RSS&q=artificial+general+intelligence",
        "AI_Safety": "https://www.bing.com/news/search?format=RSS&q=AI+safety+research"
    },
    
    # Industry & Funding
    "funding": {
        "AI_Funding": "https://www.bing.com/news/search?format=RSS&q=AI+startup+funding+investment",
        "AI_IPO": "https://www.bing.com/news/search?format=RSS&q=AI+company+IPO+public",
        "AI_Acquisition": "https://www.bing.com/news/search?format=RSS&q=AI+company+acquisition+merger",
        "AI_Valuation": "https://www.bing.com/news/search?format=RSS&q=AI+company+valuation+billion"
    }
}

# Generate sensors dynamically for all sources
sensors = []

for category, sources in AI_INTELLIGENCE_SOURCES.items():
    for source_name, url in sources.items():
        sensor_name = f"ai_intel_{source_name.lower()}"
        
        sensor = dagster.sensor(
            name=sensor_name,
            job=ai_intelligence_job,
            default_status=dagster.DefaultSensorStatus.RUNNING,
            minimum_interval_seconds=300  # 5 minutes - more strategic than 30 seconds
        )
        
        def create_sensor_function(url, category, source_name):
            def sensor_function():
                """Monitor AI intelligence sources for new content"""
                entries = get_rss_feed_content(url)
                
                # Process up to 5 most recent entries to avoid overwhelming
                for entry in entries[:5]:
                    if hasattr(entry, 'title') and hasattr(entry, 'published'):
                        yield dagster.RunRequest(
                            run_key=f"{source_name}_{entry.title}_{entry.published}",
                            run_config={
                                "ops": {
                                    "ai_intelligence_asset": {
                                        "config": {
                                            "entry": dict(entry),
                                            "source_category": category
                                        }
                                    }
                                }
                            }
                        )
            
            return sensor_function
        
        sensors.append(sensor(create_sensor_function(url, category, source_name)))

# Export definitions
definitions = dagster.Definitions(
    jobs=[ai_intelligence_job], 
    sensors=sensors, 
    assets=[ai_intelligence_asset]
)
