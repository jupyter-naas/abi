from src.core.modules.ontology.agents.EntityExtractorAgent import create_agent
from abi.utils.JSON import extract_json_from_completion
from pprint import pprint

agent = create_agent()

# result = agent.invoke("I am working as Freelancer. My company name is FRV SERVICES")
# data = extract_json_from_completion(result)
# print(data)

# # Check if result contains at least 2 continuants and 1 occurrent
# continuants = [entity for entity in data if entity['type'] == 'Continuant']
# occurrents = [entity for entity in data if entity['type'] == 'Occurrent']

# assert len(continuants) >= 2, "Result should contain at least 2 continuants"
# assert len(occurrents) >= 1, "Result should contain at least 1 occurrent"

# result = agent.invoke("I am working as Freelancer. My company name is FRV SERVICES")
# data = extract_json_from_completion(result)
# print(data)

# # Check if result contains at least 2 continuants and 1 occurrent
# continuants = [entity for entity in data if entity['type'] == 'Continuant']
# occurrents = [entity for entity in data if entity['type'] == 'Occurrent']

# assert len(continuants) >= 2, "Result should contain at least 2 continuants"
# assert len(occurrents) >= 1, "Result should contain at least 1 occurrent"

statement = """latest news on France today:
Major Wildfire in Southern France (Aude Region)
A devastating wildfire—France’s largest in decades—has been brought under control after sweeping through over 16,000 hectares (160 km²), an area larger than Paris 
Reuters
France 24
AP News
"""

result = agent.invoke(statement)
pprint(result)