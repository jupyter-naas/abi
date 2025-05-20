# Run Python Scripts

## Running Python Scripts with uv

There are multiple ways to run Python scripts in this project:

### Using uv

```bash
uv run python src/custom/modules/your_module_name/pipelines/your_pipeline_name.py
```

### Running Specific Applications

The Makefile provides shortcuts for running specific applications:

```bash
# Run the API
make api

# Run the SPARQL terminal
make sparql-terminal

# Run agent chat interfaces
make chat-naas-agent
make chat-supervisor-agent
make chat-ontology-agent
make chat-support-agent
```

## Writing Runnable Python Scripts

### Use the `__main__` block pattern

When creating scripts that can be run directly, use the `__main__` block pattern:

```python
# src/custom/modules/your_module_name/pipelines/your_pipeline_name.py
if __name__ == "__main__":
    from src import secret, services
    from src.core.modules.common.integrations import YourIntegration
    from abi.services.triple_store import TripleStoreService
    
    # Setup dependencies
    integration = YourIntegration(YourIntegrationConfiguration(...))
    triple_store = services.triple_store_service
    
    # Create pipeline configuration
    config = YourPipelineConfiguration(
        integration=integration,
        triple_store=triple_store
    )
    
    # Initialize and run pipeline
    pipeline = YourPipeline(config)
    result = pipeline.run(YourPipelineParameters(
        parameter_1="test",
        parameter_2=123
    ))
    
    # Print results in Turtle format to verify ontology mapping
    print(result.serialize(format="turtle"))
```

## Debugging Tips

- Use print statements or Python's built-in `logging` module to debug your scripts
- When running scripts directly, you can use the `-v` flag with pytest for more verbose output
- For interactive debugging, you can use `import pdb; pdb.set_trace()` or `breakpoint()` in Python 3.7+
- The debugger is configured for vscode in `.vscode/launch.json`