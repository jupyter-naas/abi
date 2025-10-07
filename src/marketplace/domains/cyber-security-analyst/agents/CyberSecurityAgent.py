"""
Cyber Security Analyst Agent - Competency Question Driven

Simple, focused agent that loads competency questions from ontology as tools.
Follows the templatablesparqlquery pattern for automatic tool generation.
"""

from abi.services.agent.IntentAgent import (
    IntentAgent,
    Intent,
    IntentType,
    AgentConfiguration,
    AgentSharedState,
)
from typing import Optional
from abi import logger

NAME = "CyberSecurityAnalyst"
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/cyber-security-analyst.png"
DESCRIPTION = "Expert cyber security analyst using D3FEND-CCO ontology queries for threat intelligence"

SYSTEM_PROMPT = """# ROLE
You are a Cyber Security Analyst with expertise in:
- D3FEND defensive techniques and CCO (Common Core Ontologies)
- Threat intelligence analysis and attack vector mapping
- SPARQL-based knowledge graph querying with full audit trails

# CAPABILITIES
You have access to competency-question-driven tools that query a comprehensive cyber security knowledge graph:

**Available Queries:**
- get_critical_events: Critical severity events with attack vectors and defenses
- get_events_by_category: Filter events by category (ransomware, supply chain, data breach)
- get_defensive_techniques: D3FEND techniques for specific attack vectors
- get_event_timeline: Chronological view of all events
- get_sector_impact: Events affecting specific sectors (healthcare, finance, government)
- get_dataset_overview: Dataset statistics
- get_attack_vector_distribution: Attack vector frequency analysis

# APPROACH
1. Use the appropriate tool for each question
2. Provide actionable defensive recommendations
3. Always cite the SPARQL query for auditability
4. Map attacks to D3FEND defensive techniques

# CONTEXT
Knowledge graph contains 20 major 2025 cyber security events with D3FEND-CCO semantic mappings.
"""


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> Optional[IntentAgent]:
    """Create Cyber Security Analyst agent with competency question tools."""
    
    # Check for OpenAI API key
    import os
    if not os.getenv('OPENAI_API_KEY'):
        logger.error("OPENAI_API_KEY not found")
        return None
    
    # Import model
    from langchain_openai import ChatOpenAI
    selected_model = ChatOpenAI(
        model="gpt-4o",
        temperature=0,
        api_key=os.getenv('OPENAI_API_KEY'),
    )

    # Load competency question tools from ontology (like templatablesparqlquery)
    tools: list = []
    
    try:
        from src.core.templatablesparqlquery import get_tools
        
        # Load cyber security competency questions as tools
        cyber_tools = [
            "get_critical_events",
            "get_events_by_category",
            "get_defensive_techniques",
            "get_event_timeline",
            "get_sector_impact",
            "get_dataset_overview",
            "get_attack_vector_distribution"
        ]
        
        tools.extend(get_tools(cyber_tools))
        logger.info(f"Loaded {len(tools)} cyber security competency question tools")
        
    except Exception as e:
        logger.error(f"Error loading competency question tools: {e}")

    # Define intents for common questions
    intents: list = [
        Intent(
            intent_value="what is your name",
            intent_type=IntentType.RAW,
            intent_target="I am your Cyber Security Analyst",
        ),
        Intent(
            intent_value="hello, hi, hey",
            intent_type=IntentType.RAW,
            intent_target="👋 Hello! I'm your Cyber Security Analyst. I can analyze 2025 cyber security threats using D3FEND-CCO ontology queries. What would you like to know?",
        ),
        Intent(
            intent_value="help, what can you do, capabilities",
            intent_type=IntentType.RAW,
            intent_target="""🔒 **Cyber Security Analyst Capabilities**

I use competency-question-driven SPARQL queries against a D3FEND-CCO knowledge graph.

**Available Analyses:**
• Critical events with attack vectors
• Events by category (ransomware, supply chain, etc.)
• D3FEND defensive techniques for attack vectors
• Chronological event timeline
• Sector-specific impact (healthcare, finance, government)
• Dataset overview and statistics
• Attack vector distribution

**Example Questions:**
• "Show me critical cyber security events"
• "What ransomware attacks happened?"
• "What defensive techniques counter phishing?"
• "Show me the event timeline"
• "What attacks affected healthcare?"

All responses include SPARQL audit trails.""",
        ),
    ]

    # Configure agent
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT,
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    return CyberSecurityAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=selected_model,
        tools=tools,
        agents=[],
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class CyberSecurityAgent(IntentAgent):
    """Cyber Security Analyst Agent using competency questions."""
    pass
