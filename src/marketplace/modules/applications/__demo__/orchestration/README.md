# Data Orchestration Capability

## Overview

This module provides data orchestration capabilities for the ABI demo, implementing automated data collection, processing, and storage workflows. The orchestration system handles complex data pipelines with scheduling, monitoring, and error handling.

## Current Implementation

**Engine**: Dagster  
**Purpose**: RSS feed monitoring and data collection  
**Scope**: Demonstration of orchestration patterns for ABI

## Features

### RSS Feed Processing Pipeline

- **15 Data Sources**: Monitors RSS feeds from technology companies, AI topics, and key personalities
- **Real-time Processing**: 30-second polling intervals for timely data collection
- **Structured Storage**: Converts RSS entries to JSON with timestamp-based organization
- **Error Handling**: Robust error handling and retry logic for reliable operation

### Monitored Sources

**Technology Topics:**
- AI, LLM, Ontology, OpenAI

**Companies:**
- Google, Meta, Microsoft, Apple, Amazon
- Tesla, SpaceX, NASA, Palantir

**Personalities:**
- Elon Musk, Donald Trump

## Architecture

### Components

1. **Assets**: Data processing units that transform RSS entries into structured JSON
2. **Sensors**: Monitoring components that detect new RSS content and trigger processing
3. **Jobs**: Orchestrated workflows that coordinate asset execution
4. **Configuration**: Flexible configuration system for different data sources

### Data Flow

```
RSS Sources → Sensors → Jobs → Assets → Storage
     ↓           ↓        ↓       ↓        ↓
  External    Monitor   Queue  Process   JSON
   Feeds      Changes   Tasks   Data     Files
```

### Storage Structure

```
storage/datastore/core/modules/__demo__/rss_feed/
├── 20250115T103045_AI_Breakthrough_in_Machine_Learning.txt
├── 20250115T103112_Tesla_Quarterly_Earnings_Report.txt
├── 20250115T103200_Palantir_Government_Contract_News.txt
└── ... (query-aware timestamped JSON files)
```

### Filename Format

**Pattern**: `YYYYMMDDTHHMMSS_QueryTerm_Title.txt`

**Benefits**:
- **Chronological Sorting**: ISO 8601 compact timestamp ensures perfect time ordering
- **Query Context**: Immediately identify which sensor/topic generated the data
- **Easy Filtering**: `ls *_Palantir_*` shows all Palantir-related articles
- **Analytics Ready**: Group by query term for trend analysis
- **Debugging**: Trace data back to specific sensors and time periods

**Examples**:
```bash
# Filter by query term
ls storage/datastore/core/modules/__demo__/rss_feed/*_AI_*
ls storage/datastore/core/modules/__demo__/rss_feed/*_Tesla_*

# Filter by date range
ls storage/datastore/core/modules/__demo__/rss_feed/20250115T*

# Combined filtering
ls storage/datastore/core/modules/__demo__/rss_feed/20250115T*_Palantir_*
```

## Usage

### Prerequisites

Before starting orchestration, ensure Docker is running and local services are up:

```bash
# Start all local services (Oxigraph, PostgreSQL, Dagster)
make local-up

# This will automatically:
# - Start Oxigraph (Knowledge Graph) on http://localhost:7878
# - Start YasGUI (SPARQL Editor) on http://localhost:3000
# - Start PostgreSQL (Agent Memory) on localhost:5432
# - Start Dagster (Orchestration) on http://localhost:3001
```

### Starting Orchestration

```bash
# Start orchestration in background
make dagster-up

# Check status
make dagster-status

# View web interface
make dagster-ui
# Or open directly: http://localhost:3001
```

### Monitoring

```bash
# View logs
make dagster-logs

# Stop orchestration
make dagster-down

# Stop all local services (including Dagster and Oxigraph)
make local-down
```

### Manual Asset Execution

```bash
# Materialize all assets
make dagster-materialize

# Or run in development mode (foreground)
make dagster-dev
```

## Configuration

### Adding New RSS Sources

To add new RSS feeds to monitor:

1. Edit `definitions.py`
2. Add new URL to the RSS sources list
3. The system automatically creates sensors and processing jobs

```python
# Example: Adding a new RSS source
"https://www.bing.com/news/search?format=RSS&q=NewTopic"
```

### Customizing Processing

The asset processing logic can be customized in the `my_asset` function:

- Modify filename generation
- Change data transformation logic
- Adjust storage location
- Add validation rules

## Integration with ABI

### Relationship to ABI Pipelines

The orchestration layer complements ABI's semantic pipelines:

- **Orchestration**: Handles scheduling, monitoring, and operational concerns
- **ABI Pipelines**: Focus on semantic transformation and knowledge graph population
- **Separation**: Clean separation allows each system to excel at its purpose

### Future Integration

Planned enhancements for deeper ABI integration:

1. **Semantic Processing**: Route orchestrated data through ABI semantic pipelines
2. **Ontology Population**: Automatically populate knowledge graphs from orchestrated data
3. **Agent Integration**: Provide orchestrated data as context for ABI agents
4. **Workflow Coordination**: Coordinate between orchestration and semantic processing

## Development

### Testing

```bash
# Test orchestration components
uv run python -c "from src.core.modules.__demo__.orchestration import definitions; print('✅ Import successful')"

# Check Dagster container status
make oxigraph-status
```

### Debugging

1. **Web Interface**: Use http://localhost:3001 for visual debugging
2. **Logs**: Check `dagster.log` for detailed execution logs
3. **Asset Status**: Use `make dagster-status` for current state

### Extending

To add new orchestration capabilities:

1. Create new assets in `definitions.py`
2. Add corresponding sensors for triggering
3. Update configuration as needed
4. Test with `make dagster-status`

## Performance Considerations

- **Polling Frequency**: 30-second intervals balance timeliness with resource usage
- **Concurrent Processing**: Multiple sensors can trigger simultaneously
- **Storage Efficiency**: JSON files with timestamp organization for easy retrieval
- **Error Recovery**: Automatic retry logic prevents data loss

## Security

- **Input Validation**: RSS content is validated before processing
- **File System**: Controlled write access to designated storage areas
- **Network**: Only outbound connections to configured RSS sources
- **Isolation**: Orchestration runs in isolated processes

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure dependencies are installed with `uv sync`
2. **Port Conflicts**: Check if port 3001 is available for web interface
3. **Storage Permissions**: Verify write access to `storage/datastore/core/modules/__demo__/`
4. **Network Issues**: Check connectivity to RSS sources
5. **Docker Issues**: If services fail to start:
   ```bash
   # Check if Docker is running
   make check-docker
   
   # Clean up Docker conflicts
   make docker-cleanup
   
   # Restart services
   make local-up
   ```

### Diagnostics

```bash
# Check orchestration health
make dagster-status

# View recent logs
make dagster-logs

# Test basic functionality
make dagster-materialize
```
