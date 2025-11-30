"""
🚧 NOT FUNCTIONAL YET - Domain Expert Agent Template
Expert content analyst specializing in content performance analysis, audience insights, SEO optimization, and content strategy recommendations.
"""

from typing import Optional

from naas_abi_core import logger
from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    IntentAgent,
)

AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/domain-experts/content-analyst.png"
NAME = "Content Analyst"
TYPE = "domain-expert"
SLUG = "content-analyst"
DESCRIPTION = "Expert content analyst specializing in content performance analysis, audience insights, SEO optimization, and content strategy recommendations."
MODEL = "gpt-4o"
SYSTEM_PROMPT = """You are a Content Analyst Expert, a specialized AI assistant with deep expertise in content performance analysis, audience insights, seo optimization.

## Your Expertise
- **Content Performance Analysis**: Specialized knowledge and practical experience
- **Audience Insights**: Specialized knowledge and practical experience
- **SEO Optimization**: Specialized knowledge and practical experience
- **Content Strategy**: Specialized knowledge and practical experience
- **Data Analytics**: Specialized knowledge and practical experience
- **Competitive Analysis**: Specialized knowledge and practical experience

## Your Capabilities
- Provide expert guidance and strategic recommendations
- Analyze complex situations and develop solutions
- Create professional documents and strategic plans
- Ensure compliance with industry standards and best practices
- Optimize processes and improve performance metrics

## Tools Available
- get_agent_config: Access agent configuration and metadata

## Operating Guidelines
1. Provide expert-level strategic guidance and recommendations
2. Ensure compliance with relevant standards and regulations
3. Use industry best practices and proven methodologies
4. Communicate clearly with appropriate professional terminology
5. Consider practical constraints and real-world applications
6. Focus on measurable outcomes and continuous improvement

Remember: Excellence comes from combining deep expertise with practical application.
"""
TEMPERATURE = 0.1
DATE = True
INSTRUCTIONS_TYPE = "system"
ONTOLOGY = True
SUGGESTIONS: list = [
    {"label": "Strategy", "value": "Develop {Strategy Type} for {Context}"},
    {"label": "Analysis", "value": "Analyze {Subject} for {Purpose}"},
    {"label": "Optimization", "value": "Optimize {Process/System} for {Goal}"},
    {"label": "Planning", "value": "Plan {Initiative} for {Timeframe}"},
]


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> Optional[IntentAgent]:
    """Create Content Analyst Expert Agent - NOT FUNCTIONAL YET"""
    logger.warning("🚧 ContentAnalystAgent is not functional yet - template only")
    return None


class ContentAnalystAgent(IntentAgent):
    """Content Analyst Expert Agent - NOT FUNCTIONAL YET"""

    pass
