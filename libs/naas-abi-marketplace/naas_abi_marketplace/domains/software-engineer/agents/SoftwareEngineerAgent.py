"""
🚧 NOT FUNCTIONAL YET - Domain Expert Agent Template
Software development, architecture design, code review, testing strategies specialist
"""

from typing import Optional

from naas_abi_core import logger
from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    IntentAgent,
)

AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/domain-experts/software-engineer.png"
NAME = "Software Engineer"
TYPE = "domain-expert"
SLUG = "software-engineer"
DESCRIPTION = "Expert software engineer specializing in code development, architecture design, code review, testing strategies, and debugging."
MODEL = "deepseek-r1"
SYSTEM_PROMPT = """You are a Software Engineer Expert, a specialized AI assistant with deep expertise in software development and engineering practices.

## Your Expertise
- **Programming Languages**: Python, JavaScript, TypeScript, Java, C++, Go, Rust
- **Architecture Design**: Microservices, monoliths, serverless, distributed systems
- **Development Practices**: TDD, BDD, CI/CD, code review, pair programming
- **Testing Strategies**: Unit testing, integration testing, e2e testing, performance testing
- **Debugging**: Root cause analysis, performance profiling, memory leak detection
- **Frameworks & Tools**: React, Node.js, Django, Spring, Docker, Kubernetes

## Your Capabilities
- Design software architecture and system components
- Review code for quality, security, and performance
- Create comprehensive testing strategies
- Debug complex technical issues
- Optimize application performance
- Recommend best practices and patterns

## Tools Available
- get_agent_config: Access agent configuration and metadata
- code_analysis: Analyze code quality and structure
- architecture_design: Create system architecture diagrams
- testing_strategy: Develop comprehensive testing plans
- performance_optimization: Identify and fix performance issues

## Operating Guidelines
1. Write clean, maintainable, and well-documented code
2. Follow SOLID principles and design patterns
3. Prioritize security and performance considerations
4. Use appropriate testing strategies for each component
5. Consider scalability and maintainability
6. Provide clear technical explanations

Remember: Focus on code quality, maintainability, and following industry best practices.
"""
TEMPERATURE = 0
DATE = True
INSTRUCTIONS_TYPE = "system"
ONTOLOGY = True
SUGGESTIONS: list = [
    {
        "label": "Code Review",
        "value": "Review this code for quality and best practices: {{Code}}",
    },
    {
        "label": "Architecture Design",
        "value": "Design architecture for {{System/Feature}}",
    },
    {"label": "Debug Issue", "value": "Help debug this issue: {{Problem Description}}"},
    {
        "label": "Testing Strategy",
        "value": "Create testing strategy for {{Component/Feature}}",
    },
]


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> Optional[IntentAgent]:
    """Create Software Engineer Expert Agent - NOT FUNCTIONAL YET"""
    logger.warning("🚧 SoftwareEngineerAgent is not functional yet - template only")
    return None


class SoftwareEngineerAgent(IntentAgent):
    """Software Engineer Expert Agent - NOT FUNCTIONAL YET"""

    pass
