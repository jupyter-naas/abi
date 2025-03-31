from src.core.modules.ontology.pipelines.AddSkilltoPersonPipeline import AddSkilltoPersonPipeline, AddSkilltoPersonPipelineConfiguration, AddSkilltoPersonPipelineParameters
from src import services

# Parameters
person_uri = "http://ontology.naas.ai/abi/a68a1780-ad47-47c1-8516-3e575d3f4a8b"
skill_uri = "http://ontology.naas.ai/abi/dbc5aa3d-fe0a-448d-bc80-4b443b4dd4fb"
parameters = AddSkilltoPersonPipelineParameters(person_uri=person_uri, skill_uri=skill_uri)

# Configuration
ontology_store = services.ontology_store_service
configuration = AddSkilltoPersonPipelineConfiguration(ontology_store=ontology_store)
pipeline = AddSkilltoPersonPipeline(configuration)

# Test
pipeline.run(parameters)