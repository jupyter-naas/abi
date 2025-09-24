from langchain_openai import ChatOpenAI
from abi.services.agent.IntentAgent import (
    IntentAgent,
    Intent,
    IntentType,
    AgentConfiguration,
    AgentSharedState,
)
from fastapi import APIRouter
from typing import Optional
from pydantic import SecretStr
from enum import Enum
from src import secret

NAME = "Word"
DESCRIPTION = "A Word Assistant for creating and managing documents from templates and raw input."
MODEL = "gpt-4o"
TEMPERATURE = 0
AVATAR_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/f/fd/Microsoft_Office_Word_%282019%E2%80%93present%29.svg/2203px-Microsoft_Office_Word_%282019%E2%80%93present%29.svg.png"
SYSTEM_PROMPT = """
## Role
You are a professional document specialist skilled in creating Word documents from various input formats.

## Objective
Your primary mission is to help users create high-quality Word documents from templates, markdown, or plain text input using the tools provided.

## Context
You operate within a secure environment with access to Word integration tools for document creation, template processing, and content generation.

## Tools
- Word integration tools for document operations
- Template processing capabilities
- Markdown to Word conversion
- Plain text to Word conversion
- Document formatting and styling

## Tasks
- Create new documents from templates or blank
- Generate documents from markdown input
- Generate documents from plain text input
- Add formatted content (paragraphs, headings, tables)
- Replace placeholders in templates
- Format and style documents
- Save documents in various formats
- For any other request not covered by the tools, just say you don't have access to the feature but the user can contact support@naas.ai to get access to the feature.

## Operating Guidelines
- When introducing yourself, state your goal and list your available tools with descriptions
- Before creating or updating a document, ensure you gather required information from the user
- Provide clear guidance on document structure and formatting options
- Support both template-based and content-driven document creation
- Preserve formatting when converting from markdown or text
- Suggest appropriate styles and formatting for professional documents

## Input Format Support
- **Markdown**: Full markdown syntax including headers, lists, tables, links, and formatting
- **Plain Text**: Automatic detection of headings, bullet points, and numbered lists
- **Templates**: Support for placeholder replacement in existing Word templates

## Constraints
- Be concise and professional
- Maintain document quality standards
- Focus on clean, readable document layouts
- Always gather requirements before starting work
- Ensure proper formatting and styling consistency
"""

SUGGESTIONS: list[str] = [
    "Create a document from markdown content",
    "Generate a report from plain text",
    "Use a template with placeholder replacement",
    "Add formatted headings and paragraphs",
    "Convert markdown table to Word table"
]

def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> Optional[IntentAgent]:
    # Set model
    model = ChatOpenAI(
        model=MODEL,
        temperature=TEMPERATURE,
        api_key=SecretStr(secret.get('OPENAI_API_KEY'))
    )

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT
        )
    
    # Set shared state
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")
    
    # Initialize tools and integrations
    tools: list = []
    
    # Add Word integration tools
    from src.marketplace.applications.word.integrations.WordIntegration import WordIntegrationConfiguration, as_tools
    word_integration_config = WordIntegrationConfiguration()
    tools += as_tools(word_integration_config)

    intents: list = [
        Intent(intent_value="Create a new document", intent_type=IntentType.TOOL, intent_target="word_create_document"),
        Intent(intent_value="Generate document from markdown", intent_type=IntentType.TOOL, intent_target="word_generate_from_markdown"),
        Intent(intent_value="Generate document from text", intent_type=IntentType.TOOL, intent_target="word_generate_from_text"),
        Intent(intent_value="Add formatted paragraph", intent_type=IntentType.TOOL, intent_target="word_add_paragraph"),
        Intent(intent_value="Add heading", intent_type=IntentType.TOOL, intent_target="word_add_heading"),
        Intent(intent_value="Replace template placeholder", intent_type=IntentType.TOOL, intent_target="word_replace_placeholder"),
        Intent(intent_value="Save document", intent_type=IntentType.TOOL, intent_target="word_save_document"),
        Intent(intent_value="Get document structure", intent_type=IntentType.TOOL, intent_target="word_get_structure"),
    ]

    return WordAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools, 
        agents=[],
        intents=intents,
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=None
    ) 

class WordAgent(IntentAgent):
    def as_api(
        self, 
        router: APIRouter, 
        route_name: str = "word", 
        name: str = NAME, 
        description: str = "API endpoints to call the Word assistant completion.", 
        description_stream: str = "API endpoints to call the Word assistant stream completion.",
        tags: Optional[list[str | Enum]] = None,
    ) -> None:
        if tags is None:
            tags = []
        return super().as_api(
            router, route_name, name, description, description_stream, tags
        )
