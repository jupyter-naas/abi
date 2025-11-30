"""
🚧 NOT FUNCTIONAL YET - Domain Expert Agent Template
Expert HR professional specializing in recruitment, employee relations, policy development, and performance management.
"""

from typing import Optional

from naas_abi_core import logger
from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    IntentAgent,
)

AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/domain-experts/human-resources-manager.png"
NAME = "Human Resources"
TYPE = "domain-expert"
SLUG = "human-resources"
DESCRIPTION = "Expert HR professional specializing in recruitment, employee relations, policy development, and performance management."
MODEL = "claude-3-5-sonnet"
SYSTEM_PROMPT = """You are a Human Resources Expert, a specialized AI assistant with deep expertise in recruitment & hiring, employee relations, policy development.

## Your Expertise
- **Recruitment & Hiring**: Specialized knowledge and practical experience
- **Employee Relations**: Specialized knowledge and practical experience
- **Policy Development**: Specialized knowledge and practical experience
- **Performance Management**: Specialized knowledge and practical experience
- **Training & Development**: Specialized knowledge and practical experience
- **Compliance**: Specialized knowledge and practical experience

## Your Capabilities
- Provide expert guidance and strategic recommendations
- Analyze complex situations and develop solutions
- Create professional documents and strategic plans
- Ensure compliance with industry standards and best practices
- Optimize processes and improve performance metrics

## Tools Available
- get_agent_config: Access agent configuration and metadata
- recruitment_planning: Specialized tool for human resources tasks
- policy_development: Specialized tool for human resources tasks
- performance_evaluation: Specialized tool for human resources tasks
- training_design: Specialized tool for human resources tasks

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
    {
        "label": "Job Description",
        "value": "Create job description for {{Role/Position}}",
    },
    {
        "label": "Interview Questions",
        "value": "Develop interview questions for {{Role}}",
    },
    {"label": "HR Policy", "value": "Draft HR policy for {{Policy Area}}"},
    {
        "label": "Performance Review",
        "value": "Design performance review process for {{Department/Role}}",
    },
]


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> Optional[IntentAgent]:
    """Create Human Resources Expert Agent - NOT FUNCTIONAL YET"""
    logger.warning("🚧 HumanResourcesAgent is not functional yet - template only")
    return None


class HumanResourcesAgent(IntentAgent):
    """Human Resources Expert Agent - NOT FUNCTIONAL YET"""

    pass
