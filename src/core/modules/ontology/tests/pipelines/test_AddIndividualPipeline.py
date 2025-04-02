from src import services
from src.core.modules.ontology.pipelines.AddIndividualPipeline import AddIndividualPipeline, AddIndividualPipelineParameters, AddIndividualPipelineConfiguration

pipeline = AddIndividualPipeline(AddIndividualPipelineConfiguration(triple_store=services.triple_store_service))

class_uri = "https://www.commoncoreontologies.org/ont00000089"
class_label = "skill"
individual_label = "Ontology"

pipeline.run(AddIndividualPipelineParameters(class_uri=class_uri, class_label=class_label, individual_label=individual_label))

