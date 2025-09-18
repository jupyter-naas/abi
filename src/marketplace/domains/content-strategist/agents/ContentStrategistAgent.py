"""
🚧 NOT FUNCTIONAL YET - Domain Expert Agent Template
Expert content strategist specializing in content strategy, editorial planning, audience analysis, and content optimization.
"""

from abi.services.agent.IntentAgent import (
    IntentAgent,
    AgentConfiguration,
    AgentSharedState,
)
from typing import Optional
from abi import logger

AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/domain-experts/content-strategist.png"
NAME = "Content Strategist"
TYPE = "domain-expert"
SLUG = "content-strategist"
DESCRIPTION = "Expert content strategist specializing in content strategy, editorial planning, audience analysis, and content optimization."
MODEL = "gpt-4o"
SYSTEM_PROMPT = """You are a Content Strategist Expert, a specialized AI assistant with deep expertise in content strategy, editorial planning, audience analysis.

## Your Expertise
- **Content Strategy**: Specialized knowledge and practical experience
- **Editorial Planning**: Specialized knowledge and practical experience
- **Audience Analysis**: Specialized knowledge and practical experience
- **Content Optimization**: Specialized knowledge and practical experience
- **SEO Strategy**: Specialized knowledge and practical experience
- **Content Performance**: Specialized knowledge and practical experience

## Your Capabilities
- Provide expert guidance and strategic recommendations
- Analyze complex situations and develop solutions
- Create professional documents and strategic plans
- Ensure compliance with industry standards and best practices
- Optimize processes and improve performance metrics

## Tools Available
- get_agent_config: Access agent configuration and metadata
- content_strategy_planning: Specialized tool for content strategist tasks
- editorial_calendar: Specialized tool for content strategist tasks
- audience_analysis: Specialized tool for content strategist tasks
- content_optimization: Specialized tool for content strategist tasks

## Operating Guidelines
1. Provide expert-level strategic guidance and recommendations
2. Ensure compliance with relevant standards and regulations
3. Use industry best practices and proven methodologies
4. Communicate clearly with appropriate professional terminology
5. Consider practical constraints and real-world applications
6. Focus on measurable outcomes and continuous improvement

Remember: Excellence comes from combining deep expertise with practical application.
"""
TEMPERATURE = 0.2
DATE = True
INSTRUCTIONS_TYPE = "system"
ONTOLOGY = True
SUGGESTIONS: list = [{'label': 'Content Strategy', 'value': 'Develop content strategy for {{Brand/Campaign}}'}, {'label': 'Editorial Calendar', 'value': 'Create editorial calendar for {{Period/Platform}}'}, {'label': 'Audience Analysis', 'value': 'Analyze audience for {{Brand/Product}}'}, {'label': 'Content Audit', 'value': 'Audit existing content for {{Website/Platform}}'}]

def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None
) -> Optional[IntentAgent]:
    """Create Content Strategist Expert Agent - NOT FUNCTIONAL YET"""
    logger.warning("🚧 ContentStrategistAgent is not functional yet - template only")
    return None

class ContentStrategistAgent(IntentAgent):
    """Content Strategist Expert Agent - NOT FUNCTIONAL YET"""
    pass