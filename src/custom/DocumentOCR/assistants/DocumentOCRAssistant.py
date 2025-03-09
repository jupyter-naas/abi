from typing import List, Optional, Callable, Any
from langchain_core.tools import Tool
from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState
from langgraph.checkpoint.memory import MemorySaver
from src import secret
from abi.services.ontology_store.OntologyStorePorts import IOntologyStoreService
from src.custom.DocumentOCR.workflows.DocumentOCRWorkflow import (
    DocumentOCRWorkflow, 
    DocumentOCRWorkflowConfiguration
)
from src.custom.DocumentOCR.integrations.MistralOCRIntegration import (
    MistralOCRIntegration,
    MistralOCRIntegrationConfiguration
)
from dataclasses import dataclass, field
import os

class DocumentOCRAgent(Agent):
    """Agent for Document OCR operations.
    
    This agent provides tools for processing documents with OCR and
    answering questions about document content.
    """
    
    def __init__(self, 
                 openai_api_key: str,
                 mistral_api_key: str, 
                 storage_path: str = "/storage/datastore",
                 ontology_store: Optional[IOntologyStoreService] = None,
                 agent_shared_state: AgentSharedState = None,
                 agent_configuration: AgentConfiguration = None):
        """Initialize Document OCR Agent.
        
        Args:
            openai_api_key (str): OpenAI API key for the agent
            mistral_api_key (str): Mistral API key for OCR integration
            storage_path (str, optional): Base path for document storage
            ontology_store (IOntologyStoreService, optional): Ontology store service
            agent_shared_state (AgentSharedState, optional): Shared state for the agent
            agent_configuration (AgentConfiguration, optional): Configuration for the agent
        """
        # Configure OCR integration
        integration_config = MistralOCRIntegrationConfiguration(
            api_key=mistral_api_key,
            storage_path=storage_path
        )
        
        # Configure workflow
        workflow_config = DocumentOCRWorkflowConfiguration(
            integration_config=integration_config,
            storage_path=storage_path
        )
        
        # Create workflow
        workflow = DocumentOCRWorkflow(workflow_config)
        
        # Configure LLM
        llm = ChatOpenAI(
            openai_api_key=openai_api_key,
            model="gpt-4-0125-preview",
            temperature=0
        )
        
        # Get tools from workflow
        tools = workflow.as_tools()

        # Create agent configuration if not provided
        if agent_configuration is None:
            agent_configuration = AgentConfiguration(
                system_prompt=_SYSTEM_PROMPT
            )
        
        # Initialize the agent
        super().__init__(
            name="Document OCR Agent",
            description="Assistant for document OCR and understanding",
            chat_model=llm,
            tools=tools,
            memory=MemorySaver(),
            state=agent_shared_state or AgentSharedState(),
            configuration=agent_configuration
        )

# System prompt for the agent
_SYSTEM_PROMPT = """You are a Document OCR Assistant that can process documents and answer questions about them.

You have access to the following tools:
- process_document: Extract text from a document using OCR
- document_understanding: Answer questions about document content
- batch_process_documents: Process multiple documents in a directory

When working with file paths:
- All paths are relative to the storage directory
- Example: "reports/financial_report.pdf" (not "/storage/datastore/reports/financial_report.pdf")

Please be helpful and concise in your responses.
"""

def create_agent(
    openai_api_key: str = None,
    mistral_api_key: str = None,
    ontology_store: Optional[IOntologyStoreService] = None,
    storage_path: str = "storage/datastore",
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> Agent:
    """Create a Document OCR Agent.
    
    Args:
        openai_api_key (str, optional): OpenAI API key
        mistral_api_key (str, optional): Mistral API key
        ontology_store (IOntologyStoreService, optional): Ontology store service
        storage_path (str, optional): Base path for document storage
        agent_shared_state (AgentSharedState, optional): Shared state for the agent
        agent_configuration (AgentConfiguration, optional): Configuration for the agent
        
    Returns:
        Agent: Document OCR Agent instance
    """
    # Use provided keys or get from environment/secret
    openai_key = openai_api_key or os.environ.get("OPENAI_API_KEY") or secret.get("OPENAI_API_KEY")
    mistral_key = mistral_api_key or os.environ.get("MISTRAL_API_KEY") or secret.get("MISTRAL_API_KEY")
    
    # Create and return the agent
    return DocumentOCRAgent(
        openai_api_key=openai_key,
        mistral_api_key=mistral_key,
        storage_path=storage_path,
        ontology_store=ontology_store,
        agent_shared_state=agent_shared_state,
        agent_configuration=agent_configuration
    )

# Alias for backward compatibility
create_documentocr_agent = create_agent 