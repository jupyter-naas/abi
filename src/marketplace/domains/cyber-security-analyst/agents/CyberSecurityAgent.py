"""
Cyber Security Agent

Competency-question-driven cyber security analyst using D3FEND-CCO ontology.
Answers specific questions about cyber events from the knowledge graph.
"""

from pathlib import Path
from typing import Optional
import yaml
from rdflib import Graph

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from abi.services.agent.Agent import AgentConfiguration, AgentSharedState
from abi.services.agent.IntentAgent import IntentAgent, Intent, IntentType
from abi import logger

# Agent metadata
NAME = "CyberSecurityAnalyst"
DESCRIPTION = "Cyber security analyst answering competency questions about cyber events using D3FEND-CCO ontology"
AVATAR_URL = "https://workspace-dev-api.naas.ai/abi/assets/domain-experts/cyber-security-analyst.png"

# System prompt
SYSTEM_PROMPT = """You are a Cyber Security Analyst specializing in answering specific competency questions about cyber security events.

Your knowledge base contains cyber security event data mapped to D3FEND and CCO ontologies.

**Your core capabilities:**
1. **List Questions**: Show all available competency questions you can answer
2. **Answer by Number**: When user provides a number (1-22), execute the corresponding SPARQL query
3. **Honest Uncertainty**: If no data exists to answer a question, say "I don't know - insufficient data in the knowledge graph"

**Response style:**
- Direct and technical
- Show query results in structured format
- If SPARQL returns empty, explicitly state no matching data found
- Never fabricate data or make assumptions beyond the graph

**When user asks "what questions can you answer?":**
- Call the list_questions tool to show all 22 competency questions

**When user provides a number (e.g., "1", "question 5", "CQ10"):**
- Parse the number and call the corresponding answer_question tool
- Show the SPARQL results
- If empty, say "I don't know - no data available for this question"
"""


class CyberSecurityAgent(IntentAgent):
    """Cyber Security Analyst Agent with competency question tools."""
    pass


def load_competency_questions() -> list:
    """Load competency questions from cqs.yaml."""
    cqs_file = Path(__file__).parent.parent / "samples" / "cqs.yaml"
    
    if not cqs_file.exists():
        logger.error(f"Competency questions file not found: {cqs_file}")
        return []
    
    with open(cqs_file, 'r') as f:
        data = yaml.safe_load(f)
    
    return data.get('competency_questions', [])


def create_list_questions_tool(questions: list) -> StructuredTool:
    """Create tool to list all available competency questions."""
    
    def list_questions() -> str:
        """
        List all available competency questions about cyber security events.
        
        Returns numbered list of questions the agent can answer using SPARQL queries.
        """
        if not questions:
            return "No competency questions available."
        
        lines = ["**Available Competency Questions:**\n"]
        for i, q in enumerate(questions, 1):
            category = q.get('category', 'Unknown')
            question = q.get('question', 'No question text')
            cq_id = q.get('id', f'CQ{i}')
            lines.append(f"{i}. [{cq_id}] **{category}**: {question}")
        
        lines.append("\n*Select a question by number (e.g., '5' or 'question 10') to see the answer.*")
        return "\n".join(lines)
    
    return StructuredTool.from_function(
        func=list_questions,
        name="list_questions",
        description="List all available competency questions about cyber security events"
    )


def create_answer_question_tool(questions: list, graph: Graph) -> StructuredTool:
    """Create tool to answer a specific competency question by number."""
    
    class QuestionInput(BaseModel):
        question_number: int = Field(
            description="The question number to answer (1-22)",
            ge=1,
            le=len(questions) if questions else 22
        )
    
    def answer_question(question_number: int) -> str:
        """
        Answer a competency question by executing the corresponding SPARQL query.
        
        Args:
            question_number: The question number (1-22) to answer
        
        Returns:
            Query results or "I don't know" if no data available
        """
        if question_number < 1 or question_number > len(questions):
            return f"Invalid question number. Please choose between 1 and {len(questions)}."
        
        question = questions[question_number - 1]
        cq_id = question.get('id', f'CQ{question_number}')
        question_text = question.get('question', 'Unknown')
        category = question.get('category', 'Unknown')
        
        logger.info(f"📊 Executing SPARQL for {cq_id}: {question_text}")
        
        # Map question to SPARQL query
        sparql_query = generate_sparql_for_question(question, graph)
        
        if not sparql_query:
            return f"**{cq_id} - {category}**\n{question_text}\n\n❌ I don't know - no SPARQL query implemented for this question yet."
        
        # Execute SPARQL
        logger.debug(f"SPARQL Query:\n{sparql_query}")
        
        try:
            results = graph.query(sparql_query)
            result_list = list(results)
            
            if not result_list:
                return f"**{cq_id} - {category}**\n{question_text}\n\n❓ I don't know - no data available in the knowledge graph to answer this question."
            
            # Format results
            response = [f"**{cq_id} - {category}**", f"{question_text}\n"]
            response.append(f"**Results ({len(result_list)} found):**\n")
            
            for i, row in enumerate(result_list[:10], 1):  # Limit to 10 results
                row_data = " | ".join([f"{var}: {val}" for var, val in zip(results.vars, row)])
                response.append(f"{i}. {row_data}")
            
            if len(result_list) > 10:
                response.append(f"\n... and {len(result_list) - 10} more results")
            
            return "\n".join(response)
            
        except Exception as e:
            logger.error(f"SPARQL execution error for {cq_id}: {e}")
            return f"**{cq_id}**\n❌ Error executing query: {e}"
    
    return StructuredTool.from_function(
        func=answer_question,
        name="answer_question",
        description="Answer a specific competency question by number (1-22). Executes SPARQL query and returns results.",
        args_schema=QuestionInput
    )


def generate_sparql_for_question(question: dict, graph: Graph) -> Optional[str]:
    """
    Generate SPARQL query for a competency question.
    
    Args:
        question: Competency question dict with id, category, question, ontology_elements
        graph: RDF graph to query
    
    Returns:
        SPARQL query string or None if not implemented
    """
    cq_id = question.get('id', '')
    category = question.get('category', '')
    
    # Map competency questions to SPARQL queries
    # For now, implement basic queries for event data
    
    if cq_id in ['CQ1', 'CQ2', 'CQ3'] or 'Digital Events' in category or 'Artifact' in category:
        # Query for cyber security events
        return """
            PREFIX cse: <https://abi.cyber-security-events.org/ontology/>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX d3f: <http://d3fend.mitre.org/ontologies/d3fend.owl#>
            
            SELECT ?event ?eventName ?eventDate ?category ?severity
            WHERE {
                ?event rdf:type cse:CyberSecurityEvent ;
                       cse:eventName ?eventName ;
                       cse:eventDate ?eventDate ;
                       cse:category ?category ;
                       cse:severity ?severity .
            }
            ORDER BY DESC(?eventDate)
            LIMIT 20
        """
    
    elif cq_id in ['CQ4', 'CQ5'] or 'Temporal' in category:
        # Query for temporal sequence
        return """
            PREFIX cse: <https://abi.cyber-security-events.org/ontology/>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            
            SELECT ?event ?eventName ?eventDate ?category
            WHERE {
                ?event rdf:type cse:CyberSecurityEvent ;
                       cse:eventName ?eventName ;
                       cse:eventDate ?eventDate ;
                       cse:category ?category .
            }
            ORDER BY ?eventDate
            LIMIT 20
        """
    
    elif cq_id in ['CQ12'] or 'Countermeasures' in category or 'defensive' in question.get('question', '').lower():
        # Query for defensive techniques
        return """
            PREFIX cse: <https://abi.cyber-security-events.org/ontology/>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX d3f: <http://d3fend.mitre.org/ontologies/d3fend.owl#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            
            SELECT ?event ?eventName ?technique (GROUP_CONCAT(?vector; separator=", ") as ?attackVectors)
            WHERE {
                ?event rdf:type cse:CyberSecurityEvent ;
                       cse:eventName ?eventName ;
                       cse:defensiveTechnique ?technique .
                OPTIONAL { ?event cse:attackVector ?vector . }
            }
            GROUP BY ?event ?eventName ?technique
            LIMIT 20
        """
    
    elif 'Infrastructure' in category or cq_id in ['CQ9', 'CQ10']:
        # Query for infrastructure/sectors
        return """
            PREFIX cse: <https://abi.cyber-security-events.org/ontology/>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            
            SELECT ?event ?eventName ?sector ?severity
            WHERE {
                ?event rdf:type cse:CyberSecurityEvent ;
                       cse:eventName ?eventName ;
                       cse:affectedSector ?sector ;
                       cse:severity ?severity .
            }
            ORDER BY DESC(?severity)
            LIMIT 20
        """
    
    # Default: return all events with basic info
    return """
        PREFIX cse: <https://abi.cyber-security-events.org/ontology/>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        
        SELECT ?event ?eventName ?eventDate ?category
        WHERE {
            ?event rdf:type cse:CyberSecurityEvent ;
                   cse:eventName ?eventName ;
                   cse:eventDate ?eventDate ;
                   cse:category ?category .
        }
        ORDER BY DESC(?eventDate)
        LIMIT 20
    """


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> Optional[IntentAgent]:
    """Create Cyber Security Agent with competency question tools."""
    
    # Load model based on AI_MODE
    from src import services
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
    
    # Load competency questions
    questions = load_competency_questions()
    logger.info(f"Loaded {len(questions)} competency questions")
    
    # Load knowledge graph from triplestore
    graph = services.triple_store_service.get_instance_graph()
    logger.info(f"Loaded knowledge graph with {len(graph)} triples")
    
    # Create tools
    tools = [
        create_list_questions_tool(questions),
        create_answer_question_tool(questions, graph)
    ]
    
    # Create intents
    intents = [
        Intent(
            name="list_questions",
            type=IntentType.TOOL,
            description="User wants to see available questions or asks 'what can you answer'",
        ),
        Intent(
            name="answer_question",
            type=IntentType.TOOL,
            description="User provides a question number or asks a specific competency question",
        ),
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