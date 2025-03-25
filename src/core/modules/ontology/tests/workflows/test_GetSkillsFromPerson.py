from src import services
from src.core.modules.ontology.workflows.GetPersonSkillsWorkflow import (
    GetPersonSkillsConfigurationWorkflow, 
    GetPersonSkillsWorkflow, 
    GetPersonSkillsWorkflowParameters,
    GetSkillsPersonWorkflowParameters
)

# Init ontology store
ontology_store = services.ontology_store_service

# Init workflow
configuration = GetPersonSkillsConfigurationWorkflow(ontology_store=ontology_store)
workflow = GetPersonSkillsWorkflow(configuration)

# Test
person_name = "John Doe"
skills = workflow.get_person_skills(GetPersonSkillsWorkflowParameters(person_name=person_name))
print(skills)

skill_label = "Ontology"
persons = workflow.get_skill_persons(GetSkillsPersonWorkflowParameters(skill_label=skill_label))
print(persons)