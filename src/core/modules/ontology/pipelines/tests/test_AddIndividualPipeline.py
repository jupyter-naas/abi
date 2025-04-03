from src import services
from src.core.modules.ontology.pipelines.AddIndividualPipeline import AddIndividualPipeline, AddIndividualPipelineParameters, AddIndividualPipelineConfiguration

pipeline = AddIndividualPipeline(AddIndividualPipelineConfiguration(triple_store=services.triple_store_service))

class_uri = "https://www.commoncoreontologies.org/ont00000089"
individual_label = "Leadership"

pipeline.run(AddIndividualPipelineParameters(class_uri=class_uri, individual_label=individual_label))

