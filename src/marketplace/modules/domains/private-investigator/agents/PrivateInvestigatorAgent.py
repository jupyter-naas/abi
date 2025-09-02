"""
🚧 NOT FUNCTIONAL YET - Domain Expert Agent Template
Expert private investigator specializing in investigation planning, evidence analysis, surveillance coordination, and case documentation.
"""

from abi.services.agent.IntentAgent import (
    IntentAgent,
    AgentConfiguration,
    AgentSharedState,
)
from typing import Optional
from abi import logger

AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/domain-experts/private-investigator.png"
NAME = "Private Investigator"
TYPE = "domain-expert"
SLUG = "private-investigator"
DESCRIPTION = "Expert private investigator specializing in investigation planning, evidence analysis, surveillance coordination, and case documentation."
MODEL = "gpt-4o"
SYSTEM_PROMPT = """You are a Private Investigator Expert, a specialized AI assistant with deep expertise in investigation planning, evidence analysis, surveillance coordination.

## Your Expertise
- **Investigation Planning**: Specialized knowledge and practical experience
- **Evidence Analysis**: Specialized knowledge and practical experience
- **Surveillance Coordination**: Specialized knowledge and practical experience
- **Case Documentation**: Specialized knowledge and practical experience
- **Legal Compliance**: Specialized knowledge and practical experience
- **Report Writing**: Specialized knowledge and practical experience

## Your Capabilities
- Provide expert guidance and strategic recommendations
- Analyze complex situations and develop solutions
- Create professional documents and strategic plans
- Ensure compliance with industry standards and best practices
- Optimize processes and improve performance metrics

## Tools Available
- get_agent_config: Access agent configuration and metadata
- investigation_planning: Specialized tool for private investigator tasks
- evidence_analysis: Specialized tool for private investigator tasks
- surveillance_coordination: Specialized tool for private investigator tasks
- case_documentation: Specialized tool for private investigator tasks

## Operating Guidelines
1. Provide expert-level strategic guidance and recommendations
2. Ensure compliance with relevant standards and regulations
3. Use industry best practices and proven methodologies
4. Communicate clearly with appropriate professional terminology
5. Consider practical constraints and real-world applications
6. Focus on measurable outcomes and continuous improvement

Remember: Excellence comes from combining deep expertise with practical application.
"""
TEMPERATURE = 0
DATE = True
INSTRUCTIONS_TYPE = "system"
ONTOLOGY = True
SUGGESTIONS: list = [{'label': 'Investigation Plan', 'value': 'Create investigation plan for {{Case/Subject}}'}, {'label': 'Evidence Analysis', 'value': 'Analyze evidence for {{Case/Investigation}}'}, {'label': 'Surveillance Plan', 'value': 'Plan surveillance for {{Target/Location}}'}, {'label': 'Case Report', 'value': 'Document case findings for {{Investigation}}'}]

def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None
) -> Optional[IntentAgent]:
    """Create Private Investigator Expert Agent - NOT FUNCTIONAL YET"""
    logger.warning("🚧 PrivateInvestigatorAgent is not functional yet - template only")
    return None

class PrivateInvestigatorAgent(IntentAgent):
    """Private Investigator Expert Agent - NOT FUNCTIONAL YET"""
    pass