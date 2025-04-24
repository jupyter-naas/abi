# Run Python Scripts

## Use Poetry to run Python scripts

To run a Python script and access the poetry environment, you MUST use the command:

```bash
make sh
```

Then, you can run your script by using the command:
```bash
poetry run python src/custom/modules/your_module_name/pipelines/your_pipeline_name.py
```

## Use the `__main__` block pattern at the bottom of your script

Here is an example of how to run a pipeline in your terminal:

```python
# src/data/pipelines/YourPipeline.py
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

Terminal command:
```bash
poetry run python src/pipelines/YourPipeline.py
```