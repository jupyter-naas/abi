from src.core.modules.ontology.pipelines.AddSkilltoPersonPipeline import AddSkilltoPersonPipeline, AddSkilltoPersonPipelineConfiguration, AddSkilltoPersonPipelineParameters
from src import services

# Parameters
person_name = "Jérémy Ravenel"
skill_name = "Ontology"
parameters = AddSkilltoPersonPipelineParameters(person_name=person_name, skill_name=skill_name)

# Configuration
ontology_store = services.ontology_store_service
configuration = AddSkilltoPersonPipelineConfiguration(ontology_store=ontology_store)
pipeline = AddSkilltoPersonPipeline(configuration)

# Test
pipeline.run(parameters)