# Dagster Integration

## Overview

Dagster is integrated into ABI as a data orchestration and pipeline management tool, primarily used for automating data ingestion workflows. While ABI has its own pipeline architecture for semantic transformation, Dagster provides additional capabilities for workflow orchestration, scheduling, and monitoring of data processing tasks.

## Current Implementation

### Configuration

Dagster is configured in the project through:

- **pyproject.toml**: Dependencies for `dagster>=1.5.13` and `dagster-webserver>=1.5.13`
- **Tool configuration**: `[tool.dagster]` section with `module_name = "dagster_definitions"`

### Core Files

1. **`/workspace/dg.py`**: Main Dagster definitions file with a simple asset and sensor example
2. **`/workspace/src/core/modules/__demo__/dagster_definitions.py__`**: RSS feed processing pipeline demonstration

## Use Cases in ABI

### 1. News Feed Processing Pipeline

The primary implemented use case is an RSS feed monitoring and processing system:

**Assets:**
- `my_asset`: Processes RSS feed entries and saves them as JSON files in the `rss_feed/` directory

**Sensors:**
- Multiple sensors monitoring RSS feeds from various sources (AI, tech companies, personalities)
- Automatic triggering based on new content detection
- 30-second polling interval for each feed

**Data Sources Monitored:**
- Technology topics: Ontology, AI, LLM, OpenAI, Google, Meta, Microsoft
- Companies: Palantir, Apple, Amazon, Tesla, SpaceX, NASA  
- Personalities: Elon Musk, Donald Trump

### 2. File-based Data Processing

**Workflow:**
1. **Detection**: Sensors monitor RSS feeds for new entries
2. **Processing**: Assets process entries and convert to structured JSON
3. **Storage**: Data saved to local filesystem with timestamped filenames
4. **Format**: `YYYY-MM-DD_HH-MM-SS_Title.txt` containing full RSS entry metadata

## Integration with ABI Architecture

### Relationship to ABI Pipelines

Dagster complements but doesn't replace ABI's native pipeline architecture:

```
┌─────────────────┐
│   Workflows     │ ← Business logic layer (ABI native)
├─────────────────┤
│   Pipelines     │ ← Semantic transformation (ABI native)  
├─────────────────┤
│   Dagster       │ ← Orchestration & scheduling layer
├─────────────────┤
│  Integrations   │ ← External service communication (ABI native)
└─────────────────┘
```

**Key Differences:**

| Aspect | ABI Pipelines | Dagster |
|--------|---------------|---------|
| **Purpose** | Semantic data transformation | Workflow orchestration |
| **Focus** | RDF triple generation | Task scheduling & monitoring |
| **Data Flow** | External source → Semantic triples → Knowledge graph | Raw data → Processing → File storage |
| **Integration** | Tight coupling with ontology | Loose coupling for general workflows |

### Benefits of Dagster Integration

1. **Scheduling**: Automated execution of data collection workflows
2. **Monitoring**: Web UI for pipeline status and debugging
3. **Reliability**: Automatic retry logic and failure handling  
4. **Scalability**: Distributed execution capabilities
5. **Observability**: Detailed logging and execution history

## Development Workflow

### Running Dagster

The project includes comprehensive Makefile targets for Dagster operations:

#### Quick Start
```bash
make dev-up    # Start all development services (includes Dagster)
make dev-down  # Stop all development services
```

#### Dagster-Specific Commands
```bash
# Development
make dagster-dev              # Start Dagster in foreground (development mode)
make dagster-up               # Start Dagster in background
make dagster-down             # Stop background Dagster processes

# Monitoring & Management  
make dagster-logs             # View live Dagster logs
make dagster-status           # Check asset status
make dagster-materialize      # Trigger asset materialization

# Web Interface
make dagster-ui               # Instructions for web interface access
```

### Current Status

- **Branch**: Active development on `dagster` branch
- **Implementation**: Proof-of-concept RSS feed processing
- **Integration**: Development-stage integration with ABI core

### Development Environment

To work with Dagster in the ABI project:

1. **Dependencies**: Automatically installed via `make .venv`
2. **Python Version**: Compatible with Python 3.11+ (current project setup)
3. **Configuration**: Located in `pyproject.toml` under `[tool.dagster]`

#### Integrated Development Workflow

**Complete Development Setup:**
```bash
make .venv     # Install all dependencies
make dev-up    # Start Oxigraph + Dagster
# ✓ Oxigraph: http://localhost:7878
# ✓ Dagster:  http://localhost:3000
```

**Process Management:**
- Dagster runs in background via process management
- Automatic startup/shutdown with development services
- Log files: `dagster.log` for debugging
- Clean shutdown ensures no orphaned processes

## Future Roadmap

### Planned Enhancements

1. **Enhanced Integration**:
   - Bridge Dagster assets to ABI semantic pipelines
   - Automatic ontology population from Dagster workflows

2. **Expanded Data Sources**:
   - Database polling sensors
   - File system monitoring
   - API webhook integration

3. **Production Deployment**:
   - Containerized Dagster deployment
   - Cloud-native scheduling (Kubernetes CronJobs)
   - Integration with ABI's CI/CD pipeline

4. **Monitoring & Alerting**:
   - Integration with ABI's logging system
   - Error notification workflows
   - Performance metrics collection

## Best Practices

### When to Use Dagster vs ABI Pipelines

**Use Dagster for:**
- Time-based scheduling (crons, intervals)
- Complex workflow orchestration
- File-based data processing  
- External system monitoring
- Batch processing jobs

**Use ABI Pipelines for:**
- Semantic data transformation
- Knowledge graph population
- Real-time data processing
- Integration with ABI ontologies
- LLM tool exposure

### Implementation Guidelines

1. **Asset Naming**: Use descriptive names that reflect data lineage
2. **Configuration**: Leverage Dagster's configuration system for environments
3. **Error Handling**: Implement proper retry logic and failure notifications
4. **Documentation**: Document asset dependencies and data schemas
5. **Testing**: Create unit tests for asset logic and integration tests for workflows

## Troubleshooting

### Common Issues

**Import Errors**: Ensure all dependencies are installed in the virtual environment
```bash
make .venv  # Install all dependencies including Dagster
```

**Module Not Found**: Verify Dagster configuration points to correct module
```toml
[tool.dagster]
module_name = "dagster_definitions"  # Should match your definitions file
```

**Dagster Won't Start**: Check if ports are available and dependencies are installed
```bash
make dagster-status    # Check current status
make dagster-logs      # View error logs
lsof -i :3000         # Check if port 3000 is in use
```

**Dagster Won't Stop**: Use the cleanup commands if normal shutdown fails
```bash
make dagster-down     # Normal shutdown
# If that fails:
ps aux | grep dagster # Find remaining processes manually
```

**Background Process Issues**: The system uses process discovery rather than PID files for robustness
- `dagster-down` finds and terminates all Dagster Python processes
- `make clean` removes any leftover log files

### Getting Help

- **Documentation**: [Dagster Official Docs](https://docs.dagster.io/)
- **ABI Integration**: See `/workspace/dg.py` and demo implementation for examples
- **Community**: Dagster Slack community for general Dagster questions

## Conclusion

Dagster enhances ABI's data processing capabilities by providing robust orchestration and scheduling features. While ABI's native pipelines handle semantic transformation, Dagster excels at managing complex workflows, scheduling, and monitoring. This complementary relationship allows ABI to maintain its semantic focus while leveraging Dagster's strengths in data orchestration.