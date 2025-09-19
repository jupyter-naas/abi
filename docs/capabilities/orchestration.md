# Data Orchestration

## Overview

Data orchestration in ABI enables you to automate data collection, processing, and monitoring workflows. This capability is perfect for scheduled data ingestion, batch processing, and operational monitoring tasks that complement ABI's ontology related pipelines.

**What You Can Build:**
- Automated data collection from APIs, RSS feeds, databases
- Scheduled batch processing workflows  
- Data monitoring and alerting systems
- ETL pipelines that feed into ABI's semantic layer
- Multi-source data aggregation workflows

**When to Use Orchestration:**
- Time-based scheduling (hourly, daily, weekly data collection)
- Complex multi-step data workflows
- External system monitoring and data polling
- Batch processing that doesn't require real-time semantic transformation

## Quick Start: Explore the Demo

The best way to understand orchestration is to explore the working demo in the `__demo__` module.

### 1. Start the Demo Orchestration

```bash
# Start the complete development environment
make dev-up

# Check orchestration status
make dagster-status

# View the web interface
open http://localhost:3000
```

### 2. Explore the Demo Implementation

The demo shows RSS feed monitoring - a real-world orchestration example:

```bash
# View the orchestration code
cat src/core/abi/orchestration/definitions.py

# See the generated data
ls storage/datastore/core/modules/abi/orchestration/rss_feed/
```

### 3. Understanding the Demo

The demo orchestration:
- **Monitors 15 RSS feeds** (AI, tech companies, personalities)
- **Processes entries** into structured JSON files
- **Runs every 30 seconds** automatically
- **Stores data** with query-aware filenames for easy analysis

## Build Your Own Orchestration

Ready to create orchestration for your own module? Follow this step-by-step guide.

### Step 1: Create Your Module Structure

Following ABI's Code-Data Symmetry principle, create both code and data structures:

```bash
# Create your module code structure
mkdir -p src/core/your_module/orchestration

# Create the orchestration files
touch src/core/your_module/orchestration/__init__.py
touch src/core/your_module/orchestration/definitions.py

# Create the mirrored data storage structure
mkdir -p storage/datastore/core/modules/your_module/orchestration

# Create Dagster instance configuration
cat > storage/datastore/core/modules/your_module/orchestration/dagster.yaml << 'EOF'
# Dagster Instance Configuration for your_module
run_storage:
  module: dagster.core.storage.runs
  class: SqliteRunStorage
  config:
    base_dir: storage/datastore/core/modules/your_module/orchestration/history

event_log_storage:
  module: dagster.core.storage.event_log
  class: SqliteEventLogStorage
  config:
    base_dir: storage/datastore/core/modules/your_module/orchestration/history/runs

schedule_storage:
  module: dagster.core.storage.schedules
  class: SqliteScheduleStorage
  config:
    base_dir: storage/datastore/core/modules/your_module/orchestration/schedules

compute_logs:
  module: dagster.core.storage.local_compute_log_manager
  class: LocalComputeLogManager
  config:
    base_dir: storage/datastore/core/modules/your_module/orchestration/compute_logs

local_artifact_storage:
  module: dagster.core.storage.root
  class: LocalArtifactStorage
  config:
    base_dir: storage/datastore/core/modules/your_module/orchestration/artifacts

run_coordinator:
  module: dagster.core.run_coordinator
  class: DefaultRunCoordinator

run_launcher:
  module: dagster
  class: DefaultRunLauncher
EOF
```

### Step 2: Define Your Data Assets

Create your orchestration logic in `definitions.py`. **Choose your approach:**

#### Option A: Simple Data Collection (like the demo)
```python
import dagster
import os
import json
from datetime import datetime

class DataCollectionConfig(dagster.Config):
    api_key: str
    endpoint: str

@dagster.asset
def collect_raw_data(context: dagster.AssetExecutionContext, config: DataCollectionConfig):
    """Collect data and save as JSON files"""
    
    # Create storage directory following ABI conventions
    storage_path = "storage/datastore/core/modules/your_module/raw_data"
    os.makedirs(storage_path, exist_ok=True)
    
    # Your data collection logic
    import requests
    response = requests.get(config.endpoint, headers={"Authorization": f"Bearer {config.api_key}"})
    data = response.json()
    
    # Save with timestamp
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    filename = f"{timestamp}_collected_data.json"
    
    with open(os.path.join(storage_path, filename), "w") as f:
        f.write(json.dumps(data, indent=4))
    
    context.log.info(f"Collected {len(data)} items")
    return data

your_job = dagster.define_asset_job("data_collection_job", selection=[collect_raw_data])
```

#### Option B: Full ABI Integration (with semantic processing)
```python
import dagster
import os
import json
from datetime import datetime

# Import your actual ABI pipeline
from src.core.modules.your_module.pipelines.YourPipeline import (
    YourPipeline, 
    YourPipelineConfiguration, 
    YourPipelineParameters
)
from abi.services.triple_store.TripleStoreFactory import TripleStoreFactory

class SemanticProcessingConfig(dagster.Config):
    api_key: str
    endpoint: str

@dagster.asset
def collect_and_process_semantically(context: dagster.AssetExecutionContext, config: SemanticProcessingConfig):
    """Collect data and process through ABI semantic pipeline"""
    
    # 1. Collect raw data
    import requests
    response = requests.get(config.endpoint, headers={"Authorization": f"Bearer {config.api_key}"})
    raw_data = response.json()
    
    # 2. Set up ABI pipeline
    triple_store = TripleStoreFactory.create_triple_store()
    pipeline_config = YourPipelineConfiguration(triple_store=triple_store)
    pipeline = YourPipeline(pipeline_config)
    
    # 3. Process each item through semantic pipeline
    total_triples = 0
    for item in raw_data:
        # Map raw data to pipeline parameters
        pipeline_params = YourPipelineParameters(
            parameter_1=item['field1'],
            parameter_2=item['field2']
        )
        
        # Execute pipeline - creates semantic triples
        semantic_graph = pipeline.run(pipeline_params)
        total_triples += len(semantic_graph)
    
    context.log.info(f"Generated {total_triples} semantic triples in knowledge graph")
    return total_triples

semantic_job = dagster.define_asset_job("semantic_processing_job", selection=[collect_and_process_semantically])
```

### Step 3: Add Sensors for Automation

Add sensors to trigger your assets automatically:

```python
@dagster.sensor(
    job=your_job,
    minimum_interval_seconds=300,  # Run every 5 minutes
    default_status=dagster.DefaultSensorStatus.RUNNING
)
def your_data_sensor():
    """Sensor to trigger data collection"""
    
    # Your trigger logic (time-based, file-based, API-based)
    if should_trigger_collection():
        yield dagster.RunRequest(
            run_config={
                "ops": {
                    "your_data_asset": {
                        "config": {
                            "api_key": "your_api_key",
                            "endpoint": "https://api.example.com/data"
                        }
                    }
                }
            }
        )
    else:
        yield dagster.SkipReason("No new data to process")

# Export definitions
definitions = dagster.Definitions(
    jobs=[your_job], 
    sensors=[your_data_sensor], 
    assets=[your_data_asset]
)
```

### Step 4: Configure Your Module

Update your module's `__init__.py`:

```python
"""
Your Module Orchestration

This module provides orchestration for [describe your use case].
"""

from .definitions import definitions

__all__ = ["definitions"]
```

### Step 5: Register Your Orchestration

Update the main orchestration configuration to include your module:

```python
# In scripts/generate_dagster_command.py or main config
# The system will automatically discover your orchestration definitions
```

### Step 6: Test Your Orchestration

```bash
# Test your orchestration with proper DAGSTER_HOME
DAGSTER_HOME=$(pwd)/storage/datastore/core/modules/your_module/orchestration \
  uv run dagster asset list -m src.core.modules.your_module.orchestration.definitions

# Start your orchestration
DAGSTER_HOME=$(pwd)/storage/datastore/core/modules/your_module/orchestration \
  uv run dagster dev

# Monitor in web interface
open http://localhost:3000
```

**Note**: Each module has its own isolated Dagster instance with its own configuration and storage.

## ABI's Code-Data Symmetry Architecture

ABI follows a **Code-Data Symmetry** principle where every orchestration component in a module has a mirrored folder structure in storage.

> 📖 **For complete details**, see [Code-Data Symmetry Architecture](../developer_tool_chain/code_data_symmetry.md)

```
Code Structure:                           Data Structure:
src/core/your_module/             storage/datastore/core/modules/your_module/
├── orchestration/                        ├── orchestration/
│   ├── definitions.py                    │   ├── dagster.yaml          # Instance config
│   ├── __init__.py                       │   ├── history/              # Run logs
│   └── README.md                         │   ├── schedules/            # Scheduler data
├── pipelines/                            │   ├── compute_logs/         # Asset logs
├── workflows/                            │   └── artifacts/            # Asset storage
└── agents/                               ├── raw_data/                 # Collected data
                                          └── processed_data/           # Pipeline output
```

**Benefits of this architecture:**
- ✅ **Predictable data location** - developers know exactly where data lives
- ✅ **Module isolation** - each module's data is self-contained  
- ✅ **Scalable architecture** - adding modules automatically creates proper data structure
- ✅ **Clear ownership** - data belongs to the module that creates it
- ✅ **No root pollution** - no temporary directories cluttering the project

## Common Orchestration Patterns

### Pattern 1: API Data Collection

Perfect for collecting data from REST APIs on a schedule:

```python
@dagster.asset
def api_data_collector(context, config: ApiConfig):
    """Collect data from external API"""
    response = requests.get(config.api_url, headers={"Authorization": f"Bearer {config.token}"})
    data = response.json()
    
    # Store with timestamp and source context
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    filename = f"{timestamp}_{config.source_name}_{data['id']}.json"
    # ... storage logic
```

### Pattern 2: Database Polling

Monitor database changes and extract new records:

```python
@dagster.sensor(minimum_interval_seconds=600)  # Every 10 minutes
def database_change_sensor():
    """Monitor database for new records"""
    last_processed = get_last_processed_timestamp()
    new_records = query_database_since(last_processed)
    
    if new_records:
        yield dagster.RunRequest(run_config={"records": new_records})
```

### Pattern 3: File System Monitoring

Watch directories for new files and process them:

```python
@dagster.sensor
def file_watcher_sensor():
    """Process new files in watched directory"""
    watch_dir = "data/incoming/"
    new_files = [f for f in os.listdir(watch_dir) if not f.startswith('.processed')]
    
    for file in new_files:
        yield dagster.RunRequest(
            run_key=file,
            run_config={"file_path": os.path.join(watch_dir, file)}
        )
```

### Pattern 4: Multi-Source Aggregation

Combine data from multiple sources into unified datasets:

```python
@dagster.asset(deps=[source_a_asset, source_b_asset, source_c_asset])
def aggregated_dataset(context):
    """Combine data from multiple sources"""
    # Load data from each source
    data_a = load_latest_data("source_a")
    data_b = load_latest_data("source_b") 
    data_c = load_latest_data("source_c")
    
    # Combine and process
    combined = merge_datasets(data_a, data_b, data_c)
    return save_aggregated_data(combined)
```

## Integration with ABI Architecture

### How Orchestration Fits with ABI

Orchestration works alongside ABI's other capabilities to create complete data workflows:

```
Raw Data Sources → Orchestration → ABI Pipelines → Knowledge Graph
     ↓                 ↓              ↓              ↓
  APIs, Files,    Schedule &      Semantic        Queryable
  Databases      Collect Data   Transformation    Knowledge
```

### Connecting Orchestration to ABI Pipelines

**REALITY CHECK**: The current demo orchestration is completely isolated - it only saves JSON files. True ABI integration requires connecting to the semantic layer.

Here's how to ACTUALLY connect orchestration to ABI pipelines:

```python
@dagster.asset
def collect_api_data(context, config: ApiConfig):
    """Orchestration: Collect raw data from API"""
    import requests
    
    response = requests.get(config.api_url)
    data = response.json()
    
    # Save raw data for processing
    storage_path = "storage/datastore/core/modules/your_module/raw_data"
    os.makedirs(storage_path, exist_ok=True)
    
    filename = f"{datetime.now().strftime('%Y%m%dT%H%M%S')}_raw_data.json"
    with open(os.path.join(storage_path, filename), "w") as f:
        f.write(json.dumps(data, indent=4))
    
    return data

@dagster.asset(deps=[collect_api_data])
def process_with_abi_pipeline(context):
    """Bridge: Process data through ABI semantic pipeline"""
    
    # Import your actual ABI pipeline
    from src.core.modules.your_module.pipelines.YourPipeline import (
        YourPipeline, 
        YourPipelineConfiguration, 
        YourPipelineParameters
    )
    from abi.services.triple_store.TripleStoreFactory import TripleStoreFactory
    
    # Get ABI services (triple store, etc.)
    triple_store = TripleStoreFactory.create_triple_store()
    
    # Configure the pipeline
    pipeline_config = YourPipelineConfiguration(
        triple_store=triple_store
    )
    pipeline = YourPipeline(pipeline_config)
    
    # Load the raw data
    raw_data = load_latest_raw_data()  # Your data loading logic
    
    # Convert to pipeline parameters
    pipeline_params = YourPipelineParameters(
        # Map your raw data to pipeline parameters
        parameter_1=raw_data['field1'],
        parameter_2=raw_data['field2']
    )
    
    # Execute ABI pipeline - returns RDF Graph
    semantic_graph = pipeline.run(pipeline_params)
    
    context.log.info(f"Generated {len(semantic_graph)} semantic triples")
    
    # Data is now in the knowledge graph via triple_store.insert()
    return semantic_graph
```

**Key Requirements for Real Integration:**

1. **Import actual ABI pipeline classes** from your module
2. **Configure pipeline with ABI services** (triple_store, etc.)
3. **Map raw data to PipelineParameters** - each pipeline has specific parameter requirements
4. **Call `pipeline.run(parameters)`** - returns RDF Graph
5. **Pipeline automatically stores triples** in knowledge graph via `triple_store.insert()`

### Best Practices for Integration

**Use Orchestration For:**
- ✅ Scheduled data collection (hourly, daily, weekly)
- ✅ External API polling and monitoring
- ✅ Batch file processing
- ✅ Data aggregation from multiple sources
- ✅ ETL workflows that feed ABI pipelines

**Use ABI Pipelines For:**
- ✅ Converting raw data to semantic triples
- ✅ Real-time data transformation
- ✅ Knowledge graph population
- ✅ Ontology-aware processing
- ✅ LLM tool integration

## Managing Your Orchestration

### Essential Commands

```bash
# Start orchestration environment
make dev-up                   # Start all services (includes orchestration)

# Monitor your orchestration
make dagster-status           # Check asset status
make dagster-logs             # View live logs
open http://localhost:3000    # Web interface

# Control orchestration
make dagster-up               # Start orchestration only
make dagster-down             # Stop orchestration
make dagster-materialize      # Manually trigger assets
```

### Web Interface

The orchestration web interface at `http://localhost:3000` provides:

- **Asset Lineage**: Visual representation of your data dependencies
- **Run History**: See all executions with success/failure status
- **Logs**: Detailed logs for debugging and monitoring
- **Asset Catalog**: Browse all your data assets and their metadata
- **Sensors**: Monitor sensor status and trigger history

### Monitoring and Debugging

**Check Asset Status:**
```bash
make dagster-status
# Shows: my_asset (and any other assets you've created)
```

**View Logs:**
```bash
make dagster-logs
# Shows real-time orchestration logs
```

**Manual Testing:**
```bash
# Test a specific asset manually
make dagster-materialize
```

**Debug Storage:**
```bash
# Check generated data
ls storage/datastore/core/modules/your_module/

# Check orchestration logs and history
ls storage/datastore/core/modules/your_module/orchestration/history/

# Check asset storage
ls storage/datastore/core/modules/your_module/orchestration/artifacts/
```

## Advanced Topics

### Error Handling and Retries

Make your orchestration robust with proper error handling:

```python
@dagster.asset(
    retry_policy=dagster.RetryPolicy(max_retries=3, delay=60)
)
def robust_data_collector(context):
    """Asset with automatic retry on failure"""
    try:
        data = fetch_external_data()
        return process_data(data)
    except Exception as e:
        context.log.error(f"Data collection failed: {e}")
        raise  # Will trigger retry
```

### Configuration Management

Use Dagster's configuration system for different environments:

```python
class ProductionConfig(dagster.Config):
    api_endpoint: str = "https://api.production.com"
    batch_size: int = 1000
    
class DevelopmentConfig(dagster.Config):
    api_endpoint: str = "https://api.staging.com"
    batch_size: int = 100

@dagster.asset
def configurable_asset(context, config: ProductionConfig):
    """Asset that adapts to different environments"""
    # Use config.api_endpoint and config.batch_size
```

### Asset Dependencies

Create complex workflows with asset dependencies:

```python
@dagster.asset
def raw_data():
    """Collect raw data"""
    return fetch_raw_data()

@dagster.asset(deps=[raw_data])
def processed_data():
    """Process the raw data"""
    raw = load_asset_data("raw_data")
    return process(raw)

@dagster.asset(deps=[processed_data])
def final_output():
    """Create final output"""
    processed = load_asset_data("processed_data")
    return finalize(processed)
```

### Performance Optimization

Optimize your orchestration for large-scale data processing:

```python
@dagster.asset(
    partitions_def=dagster.DailyPartitionsDefinition(start_date="2024-01-01")
)
def daily_data_asset(context):
    """Process data in daily partitions for better performance"""
    partition_date = context.partition_key
    return process_data_for_date(partition_date)
```

## Troubleshooting

### Common Issues

**My orchestration won't start:**
```bash
# Check if dependencies are installed
make .venv

# Verify orchestration status
make dagster-status

# Check for port conflicts
lsof -i :3000
```

**Assets aren't running automatically:**
- Check sensor status in web interface (`http://localhost:3000`)
- Verify sensor `default_status=dagster.DefaultSensorStatus.RUNNING`
- Check sensor logs for errors

**Data isn't being saved:**
```bash
# Check storage directory exists and is writable
ls -la storage/datastore/core/modules/your_module/

# Verify file paths in your asset code
# Check logs for permission errors
make dagster-logs
```

**Configuration errors:**
- Ensure your `Config` class matches the data you're passing
- Check `run_config` structure in sensors
- Validate JSON serializable data types

**Import errors in your module:**
- Verify your module structure follows ABI conventions
- Check `__init__.py` files exist
- Ensure proper Python path setup

### Getting Help

**Learning Resources:**
- Explore the working demo: `src/core/abi/orchestration/`
- Check generated data: `storage/datastore/core/modules/abi/orchestration/rss_feed/`
- Web interface: `http://localhost:3000` (when running)

**Debugging Steps:**
1. Start with the demo to understand the patterns
2. Copy and modify demo code for your use case
3. Test manually with `make dagster-materialize`
4. Use web interface for visual debugging
5. Check logs with `make dagster-logs`

## Next Steps

1. **Explore the Demo**: Start with `make dev-up` and explore the working RSS example
2. **Build Your First Orchestration**: Follow the step-by-step guide above
3. **Connect to ABI Pipelines**: Bridge your orchestrated data into semantic processing
4. **Scale Up**: Add more sensors, assets, and complex workflows as needed

Orchestration in ABI gives you the power to automate data collection and processing at scale, while maintaining clean integration with ABI's semantic capabilities.