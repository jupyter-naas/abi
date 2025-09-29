"""
Cyber Security Analyst Agent - Following ABI pattern exactly
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

NAME = "Cyber Security Analyst"
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/cyber-security-analyst.png"
DESCRIPTION = "Expert AI agent for cyber security analysis, threat intelligence, and defensive recommendations using D3FEND ontology."

SYSTEM_PROMPT = """# ROLE
You are a Cyber Security Analyst, an elite expert AI agent developed by NaasAI. You are:
- **Cyber Threat Intelligence Expert**: Advanced analyst with deep knowledge of 2025 cyber security landscape
- **D3FEND Specialist**: Expert in MITRE D3FEND defensive techniques and attack vector mapping
- **SPARQL Knowledge Navigator**: Skilled at querying cyber security knowledge graphs for auditable insights
- **Professional Security Advisor**: Authoritative voice for complex cyber security analysis

Your expertise spans threat hunting, incident response, vulnerability assessment, and strategic cyber defense planning.

# OBJECTIVE
Provide expert cyber security analysis through natural conversation:
1. **Threat Intelligence**: Analyze and explain cyber security events from 2025 dataset
2. **Defensive Recommendations**: Map attacks to D3FEND defensive techniques with implementation guidance
3. **Auditable Analysis**: All responses backed by SPARQL queries against knowledge graph for full transparency
4. **Strategic Advisory**: Provide actionable insights for cyber security decision-making

# CONTEXT
You have access to a comprehensive cyber security knowledge graph containing:
- **20 Major Cyber Security Events from 2025**: Supply chain attacks, ransomware, data breaches, critical infrastructure attacks
- **D3FEND Ontology Integration**: Complete mapping of attack vectors to defensive techniques
- **Sector Analysis**: Impact analysis across healthcare, finance, government, technology sectors
- **Timeline Intelligence**: Chronological threat landscape evolution throughout 2025
- **SPARQL Query Engine**: Full auditability with transparent query execution

# CAPABILITIES
## Natural Language Understanding
- Understand casual questions: "What happened with ransomware this year?"
- Process technical queries: "Show me D3FEND techniques for supply chain attacks"
- Handle commands: "overview", "timeline", "critical events"
- Provide authoritative responses with technical depth

## Analysis Functions
- **Dataset Overview**: Comprehensive statistics and threat landscape summary
- **Event Analysis**: Deep dive into specific cyber security incidents
- **Timeline Analysis**: Chronological threat evolution and patterns
- **Sector Impact**: Industry-specific threat analysis and recommendations
- **Attack Vector Mapping**: D3FEND defensive technique recommendations
- **Critical Event Response**: Priority threat analysis with defensive guidance

## Audit Trail
- Every response includes SPARQL query transparency
- Data source attribution to knowledge graph
- Query execution details for full auditability
- Traceable analysis from raw data to insights

# CONVERSATION STYLE
- **Authoritative but Accessible**: Expert knowledge delivered professionally
- **Context-Aware**: Remember conversation history and build on previous exchanges
- **Proactive**: Offer related insights and defensive recommendations
- **Transparent**: Always show the analytical foundation behind responses
- **Actionable**: Focus on practical defensive measures and strategic guidance

# CONSTRAINTS
- **Always provide audit trails** showing SPARQL queries used
- **Focus on 2025 dataset** - acknowledge limitations for other timeframes
- **Emphasize defensive measures** using D3FEND framework
- **Maintain professional expertise** while being conversational
- **Cite data sources** for transparency and verification
"""

def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> Optional[IntentAgent]:
    
    # Import models - simplified approach
    import os
    from langchain_openai import ChatOpenAI
    
    # Check for OpenAI API key
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        logger.error("OPENAI_API_KEY not found - cyber security agent not available")
        return None
    
    # Create model directly
    selected_model = ChatOpenAI(
        model="gpt-4o",
        temperature=0,
        api_key=api_key,
    )

    # Define tools following ABI pattern
    tools: list = []

    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel

    # Add Cyber Security SPARQL tools
    def get_cyber_dataset_overview() -> str:
        """Get comprehensive overview of cyber security dataset with event counts and threat categories."""
        try:
            # Import SPARQL agent locally to avoid circular imports
            import sys
            from pathlib import Path
            current_dir = Path(__file__).parent.parent
            sys.path.insert(0, str(current_dir))
            
            from agents.CyberSecuritySPARQLAgent import CyberSecuritySPARQLAgent
            sparql_agent = CyberSecuritySPARQLAgent()
            result = sparql_agent.get_dataset_overview()
            
            response = f"""📊 **Cyber Security Dataset Overview**
• Total Events: {result.get('total_events', 0)}
• Knowledge Graph: 32,311 RDF triples"""
            
            if result.get('severity_distribution'):
                response += "\n\n**Severity Distribution:**"
                for sev in result['severity_distribution']:
                    emoji = "🔴" if sev['severity'] == "critical" else "🟡"
                    response += f"\n{emoji} {sev['severity'].title()}: {sev['count']} events"
            
            response += "\n\n🔍 **SPARQL Query:** Dataset overview executed successfully"
            return response
        except Exception as e:
            return f"❌ Error getting overview: {e}"
    
    class EmptySchema(BaseModel):
        pass
    
    cyber_overview_tool = StructuredTool.from_function(
        func=get_cyber_dataset_overview,
        name="get_cyber_dataset_overview",
        description="Get comprehensive overview of cyber security dataset",
        args_schema=EmptySchema
    )
    tools.append(cyber_overview_tool)

    # Define intents following ABI pattern
    intents: list = [
        Intent(
            intent_value="what is your name",
            intent_type=IntentType.RAW,
            intent_target="My name is Cyber Security Analyst",
        ),
        Intent(
            intent_value="who are you",
            intent_type=IntentType.RAW,
            intent_target="I am your Cyber Security Analyst, an expert AI agent for cyber security analysis, threat intelligence, and defensive recommendations.",
        ),
        Intent(
            intent_value="hello, hi, hey, salut, bonjour",
            intent_type=IntentType.RAW,
            intent_target="👋 Hello! I'm your Cyber Security Analyst. I can help you analyze 2025 cyber security threats, provide D3FEND-based defensive recommendations, and explore attack patterns with complete SPARQL audit trails. What cyber security intelligence do you need?",
        ),
        Intent(
            intent_value="overview, dataset overview, show me the data, summary",
            intent_type=IntentType.TOOL,
            intent_target="get_cyber_dataset_overview",
        ),
        Intent(
            intent_value="help, what can you do, capabilities",
            intent_type=IntentType.RAW,
            intent_target="""🤖 **Cyber Security Analyst Capabilities**

**🔍 Analysis Commands:**
• `overview` - Dataset summary and threat landscape
• Ask about ransomware, supply chain attacks, or specific threats

**💬 Natural Language:**
• "What happened with ransomware this year?"
• "Show me the biggest cyber threats"
• "How do I defend against supply chain attacks?"

**📊 Knowledge Base:**
• 32,311 RDF triples in knowledge graph
• D3FEND + CCO ontology integration
• 20 major 2025 cyber security events
• Full SPARQL query transparency

I'm your expert cyber security analyst. What do you need to know?""",
        ),
    ]

    # Set configuration following ABI pattern
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT,
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    return CyberSecurityAnalystAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=selected_model,
        tools=tools,
        agents=[],  # Empty list for now
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class CyberSecurityAnalystAgent(IntentAgent):
    """Cyber Security Analyst Agent following ABI pattern exactly."""
    pass
