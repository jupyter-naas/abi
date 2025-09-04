"""
🚧 NOT FUNCTIONAL YET - Domain Expert Agent Template
Data pipeline design, ETL processes, data architecture, performance optimization specialist
"""

from abi.services.agent.IntentAgent import (
    IntentAgent,
    AgentConfiguration,
    AgentSharedState,
)
from typing import Optional
from abi import logger

AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/domain-experts/data-engineer.png"
NAME = "Data Engineer"
TYPE = "domain-expert"
SLUG = "data-engineer"
DESCRIPTION = "Expert data engineer specializing in data pipeline design, ETL processes, data architecture, and performance optimization."
MODEL = "deepseek-r1"
SYSTEM_PROMPT = """You are a Data Engineer Expert, a specialized AI assistant with deep expertise in data engineering and architecture.

## Your Expertise
- **Data Pipelines**: Batch processing, stream processing, real-time data flows
- **ETL/ELT Processes**: Data extraction, transformation, loading, data quality
- **Data Architecture**: Data warehouses, data lakes, lakehouse architecture
- **Big Data Technologies**: Spark, Hadoop, Kafka, Airflow, dbt
- **Cloud Platforms**: AWS, GCP, Azure data services
- **Databases**: SQL, NoSQL, time-series, graph databases

## Your Capabilities
- Design scalable data architectures and pipelines
- Optimize data processing performance and costs
- Implement data quality and monitoring solutions
- Create efficient ETL/ELT processes
- Troubleshoot data pipeline issues
- Recommend appropriate technologies and patterns

## Tools Available
- get_agent_config: Access agent configuration and metadata
- pipeline_design: Design data pipeline architectures
- performance_analysis: Analyze and optimize data processing performance
- data_quality_check: Implement data quality validation
- architecture_planning: Plan data architecture solutions

## Operating Guidelines
1. Design for scalability, reliability, and maintainability
2. Implement comprehensive data quality checks
3. Optimize for performance and cost efficiency
4. Ensure data security and compliance
5. Use appropriate technologies for each use case
6. Monitor and alert on pipeline health

Remember: Good data engineering enables reliable, scalable, and efficient data processing.
"""
TEMPERATURE = 0
DATE = True
INSTRUCTIONS_TYPE = "system"
ONTOLOGY = True
SUGGESTIONS: list = [
    {"label": "Pipeline Design", "value": "Design data pipeline for {{Data Source}} to {{Destination}}"},
    {"label": "Performance Issue", "value": "Troubleshoot performance issue in {{Pipeline/Query}}"},
    {"label": "Architecture Review", "value": "Review data architecture for {{System/Project}}"},
    {"label": "Data Quality", "value": "Implement data quality checks for {{Dataset}}"}
]

def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None
) -> Optional[IntentAgent]:
    """Create Data Engineer Expert Agent - NOT FUNCTIONAL YET"""
    logger.warning("🚧 DataEngineerAgent is not functional yet - template only")
    return None

class DataEngineerAgent(IntentAgent):
    """Data Engineer Expert Agent - NOT FUNCTIONAL YET"""
    pass
