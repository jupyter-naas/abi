from abi.services.agent.Agent import Agent, AgentConfiguration
from langchain_openai import ChatOpenAI

with open("src/custom/modules/phases/ontologies/phases.ttl", "r") as f:
    ontology = f.read()

class PhasesAgent(Agent):
    
    DEFAULT_SYSTEM_PROMPT = """
You are PHASES, a helpful assistant helping users to do research. You are backed by the PHASES ontology.

```phases_ontology
{ontology}
```
    """
    
    @staticmethod
    def new():
        
        model = ChatOpenAI(
            model="gpt-4.1-mini",
        )
        
        return PhasesAgent(
            name="PhasesAgent",
            description="PhasesAgent is a agent that can help you with your phases",
            chat_model=model,
            configuration=AgentConfiguration(
                system_prompt=PhasesAgent.DEFAULT_SYSTEM_PROMPT.format(ontology=ontology),
            ),
        )
        
        
create_agent = PhasesAgent.new