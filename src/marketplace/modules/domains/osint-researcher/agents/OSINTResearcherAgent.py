"""
🚧 NOT FUNCTIONAL YET - Domain Expert Agent Template
Expert OSINT researcher specializing in open source intelligence, information gathering, threat analysis, and digital forensics.
"""

from abi.services.agent.IntentAgent import (
    IntentAgent,
    AgentConfiguration,
    AgentSharedState,
)
from typing import Optional
from abi import logger

AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/domain-experts/osint-researcher.png"
NAME = "OSINT Researcher"
TYPE = "domain-expert"
SLUG = "osint-researcher"
DESCRIPTION = "Expert OSINT researcher specializing in open source intelligence, information gathering, threat analysis, and digital forensics."
MODEL = "gpt-4o"
SYSTEM_PROMPT = """You are a OSINT Researcher Expert, a specialized AI assistant with deep expertise in open source intelligence, information gathering, threat analysis.

## Your Expertise
- **Open Source Intelligence**: Specialized knowledge and practical experience
- **Information Gathering**: Specialized knowledge and practical experience
- **Threat Analysis**: Specialized knowledge and practical experience
- **Digital Forensics**: Specialized knowledge and practical experience
- **Social Media Intelligence**: Specialized knowledge and practical experience
- **Geospatial Analysis**: Specialized knowledge and practical experience

## Your Capabilities
- Provide expert guidance and strategic recommendations
- Analyze complex situations and develop solutions
- Create professional documents and strategic plans
- Ensure compliance with industry standards and best practices
- Optimize processes and improve performance metrics

## Tools Available
- get_agent_config: Access agent configuration and metadata
- information_gathering: Specialized tool for osint researcher tasks
- threat_analysis: Specialized tool for osint researcher tasks
- digital_forensics: Specialized tool for osint researcher tasks
- intelligence_reporting: Specialized tool for osint researcher tasks

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
SUGGESTIONS: list = [{'label': 'Intelligence Gathering', 'value': 'Gather intelligence on {{Target/Topic}}'}, {'label': 'Threat Analysis', 'value': 'Analyze threats related to {{Subject/Organization}}'}, {'label': 'Digital Investigation', 'value': 'Investigate digital footprint of {{Entity/Person}}'}, {'label': 'Intelligence Report', 'value': 'Create intelligence report on {{Topic/Investigation}}'}]

def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None
) -> Optional[IntentAgent]:
    """Create OSINT Researcher Expert Agent - NOT FUNCTIONAL YET"""
    logger.warning("🚧 OSINTResearcherAgent is not functional yet - template only")
    return None

class OSINTResearcherAgent(IntentAgent):
    """OSINT Researcher Expert Agent - NOT FUNCTIONAL YET"""
    pass