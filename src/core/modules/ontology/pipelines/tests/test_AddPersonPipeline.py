from src import services
from src.core.modules.ontology.pipelines.AddIndividualPipeline import (
    AddIndividualPipelineConfiguration,
)
from src.core.modules.ontology.pipelines.AddPersonPipeline import (
    AddPersonPipeline,
    AddPersonPipelineParameters,
    AddPersonPipelineConfiguration,
)

# Configuration
triple_store = services.triple_store_service
individual_pipeline_configuration = AddIndividualPipelineConfiguration(
    triple_store=triple_store
)

# Pipeline
pipeline = AddPersonPipeline(
    AddPersonPipelineConfiguration(
        triple_store=triple_store,
        add_individual_pipeline_configuration=individual_pipeline_configuration,
    )
)

# Run
name = "John Doe"
first_name = "John"
last_name = "Doe"
pipeline.run(
    AddPersonPipelineParameters(name=name, first_name=first_name, last_name=last_name)
)
