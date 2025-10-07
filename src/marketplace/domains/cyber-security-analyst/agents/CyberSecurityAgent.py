"""
Cyber Security Agent

Competency-question-driven cyber security analyst using D3FEND-CCO ontology.
Answers 22 specific competency questions about cyber events from the knowledge graph.
"""

from pathlib import Path
from typing import Optional

from abi.services.agent.Agent import AgentConfiguration, AgentSharedState
from abi.services.agent.IntentAgent import IntentAgent, Intent, IntentType
from abi import logger

# Agent metadata
NAME = "CyberSecurityAnalyst"
DESCRIPTION = "Cyber security analyst answering 22 competency questions about cyber events using D3FEND-CCO ontology"
AVATAR_URL = "https://workspace-dev-api.naas.ai/abi/assets/domain-experts/cyber-security-analyst.png"

# System prompt
SYSTEM_PROMPT = """You are a Cyber Security Analyst specializing in answering competency questions about cyber security events.

Your knowledge base contains cyber security event data mapped to D3FEND and CCO ontologies.

**Available Competency Questions (CQ1-CQ22):**
- CQ1-3: Digital Events (artifacts, file creation, artifact generation)
- CQ4-5: Temporal Ordering (sequence, dependencies)
- CQ6: Agent Participation
- CQ7: Artifact Lineage
- CQ8: Threat Modeling (kill chain reconstruction)
- CQ9-10: Infrastructure (elements, network correlation)
- CQ11: Causality
- CQ12: Countermeasures
- CQ13: Information Entities
- CQ14: State Changes
- CQ15-18: Data Quality (missing processes, inconsistencies, enrichment, validation)
- CQ19: Temporal Validation
- CQ20-22: Cross-Domain Context (mission processes, physical correlation, domain boundaries)

**How to use:**
- Each CQ has a corresponding tool (e.g., cq1_digital_artifacts, cq4_temporal_sequence)
- Call the appropriate tool to execute the SPARQL query
- If no data exists, say "I don't know - no data available for this competency question"

**Response style:**
- Direct and technical
- Show query results in structured format
- Never fabricate data or make assumptions beyond the graph
"""


class CyberSecurityAgent(IntentAgent):
    """Cyber Security Analyst Agent with 22 competency question tools."""
    pass


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> Optional[IntentAgent]:
    """Create Cyber Security Agent with all 22 competency question tools."""
    
    # Load model based on AI_MODE
    from os import getenv
    
    ai_mode = getenv("AI_MODE", "cloud")
    
    if ai_mode == "local":
        from abi.services.chat_model.adaptors.secondary.ollama.OllamaModel import OllamaModel
        model_name = getenv("LOCAL_MODEL", "llama3.2")
        selected_model = OllamaModel(model=model_name, temperature=0.0)
        logger.info(f"Using local model: {model_name}")
    else:
        from abi.services.chat_model.adaptors.secondary.openai.OpenAIModel import OpenAIModel
        selected_model = OpenAIModel(model="gpt-4o", temperature=0.0)
        logger.info("Using OpenAI model: gpt-4o")
    
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()
    
    # Load all 22 competency question tools from CyberSecurityQueries.ttl
    from src.core.templatablesparqlquery import get_tools
    
    ontology_file = Path(__file__).parent.parent / "ontologies" / "CyberSecurityQueries.ttl"
    
    # All 22 competency questions as tools
    cq_tools = [
        "cq1_digital_artifacts",
        "cq2_file_creation_processes",
        "cq3_artifact_generation",
        "cq4_temporal_sequence",
        "cq5_temporal_dependencies",
        "cq6_agent_participation",
        "cq7_artifact_lineage",
        "cq8_kill_chain",
        "cq9_infrastructure",
        "cq10_network_correlation",
        "cq11_causality",
        "cq12_countermeasures",
        "cq13_information_entities",
        "cq14_state_changes",
        "cq15_missing_processes",
        "cq16_inconsistencies",
        "cq17_data_enrichment",
        "cq18_data_validation",
        "cq19_temporal_validation",
        "cq20_mission_context",
        "cq21_physical_correlation",
        "cq22_cross_domain",
    ]
    
    tools = get_tools(cq_tools, ontology_file_path=str(ontology_file))
    logger.info(f"Loaded {len(tools)} competency question tools")
    
    # Create intents - map all CQ tools to TOOL intent type
    intents = [
        Intent(
            name=tool_name,
            type=IntentType.TOOL,
            description=f"Answer competency question {tool_name}",
        )
        for tool_name in cq_tools
    ]
    
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
        system_prompt=SYSTEM_PROMPT,
    )