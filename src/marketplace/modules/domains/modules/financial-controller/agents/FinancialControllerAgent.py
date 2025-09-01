"""
🚧 NOT FUNCTIONAL YET - Domain Expert Agent Template
Expert financial controller specializing in financial planning, budgeting, cost analysis, financial controls, and reporting.
"""

from abi.services.agent.IntentAgent import (
    IntentAgent,
    AgentConfiguration,
    AgentSharedState,
)
from typing import Optional
from abi import logger

AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/domain-experts/financial-controller.png"
NAME = "Financial Controller"
TYPE = "domain-expert"
SLUG = "financial-controller"
DESCRIPTION = "Expert financial controller specializing in financial planning, budgeting, cost analysis, financial controls, and reporting."
MODEL = "gpt-4o"
SYSTEM_PROMPT = """You are a Financial Controller Expert, a specialized AI assistant with deep expertise in financial planning, budgeting, cost analysis.

## Your Expertise
- **Financial Planning**: Specialized knowledge and practical experience
- **Budgeting**: Specialized knowledge and practical experience
- **Cost Analysis**: Specialized knowledge and practical experience
- **Financial Controls**: Specialized knowledge and practical experience
- **Financial Reporting**: Specialized knowledge and practical experience
- **Variance Analysis**: Specialized knowledge and practical experience

## Your Capabilities
- Provide expert guidance and strategic recommendations
- Analyze complex situations and develop solutions
- Create professional documents and strategic plans
- Ensure compliance with industry standards and best practices
- Optimize processes and improve performance metrics

## Tools Available
- get_agent_config: Access agent configuration and metadata
- financial_planning: Specialized tool for financial controller tasks
- budget_creation: Specialized tool for financial controller tasks
- cost_analysis: Specialized tool for financial controller tasks
- financial_controls: Specialized tool for financial controller tasks

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
SUGGESTIONS: list = [{'label': 'Budget Planning', 'value': 'Create budget plan for {{Department/Project}}'}, {'label': 'Cost Analysis', 'value': 'Analyze costs for {{Process/Department}}'}, {'label': 'Financial Controls', 'value': 'Design financial controls for {{Area/Process}}'}, {'label': 'Variance Analysis', 'value': 'Analyze budget variance for {{Period/Department}}'}]

def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None
) -> Optional[IntentAgent]:
    """Create Financial Controller Expert Agent - NOT FUNCTIONAL YET"""
    logger.warning("🚧 FinancialControllerAgent is not functional yet - template only")
    return None

class FinancialControllerAgent(IntentAgent):
    """Financial Controller Expert Agent - NOT FUNCTIONAL YET"""
    pass