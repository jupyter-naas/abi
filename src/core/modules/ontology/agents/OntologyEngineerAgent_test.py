from src.core.modules.ontology.agents.OntologyEngineerAgent import create_agent
from pprint import pprint

agent = create_agent()

statement = """latest news on France today:
Major Wildfire in Southern France (Aude Region)
A devastating wildfire—France’s largest in decades—has been brought under control after sweeping through over 16,000 hectares (160 km²), an area larger than Paris 
Reuters
France 24
AP News
.

The blaze struck southern France's wine country, resulting in one death, at least 13 injuries (including 11 firefighters), destruction of 36 homes, and thousands of displaced residents accommodated in emergency shelters 
AP News
+1
.

Firefighters remain on high alert amid concerns that the upcoming heatwave—with temperatures expected to exceed 30 °C—could spark flare-ups 
AP News
.

Authorities have linked the disaster to climate change, calling it the worst fire since 1949, with serious damage to vineyards and livelihoods in the Corbières region 
AP News
+1
.
"""

result = agent.invoke(statement)
pprint(result)