"""DocumentAgent — an agent that can talk over all ingested and vectorized documents.

It exposes a semantic search tool backed by the vector store collection(s)
produced by the MarkdownToVector pipeline.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
from langchain_core.tools import BaseTool, StructuredTool
from langchain_openai import OpenAIEmbeddings
from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    IntentAgent,
)
from pydantic import BaseModel, Field

NAME = "Document_Agent"
AVATAR_URL = (
    "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/document-agent.png"
)
DESCRIPTION = (
    "Answers questions about ingested documents by performing semantic search over "
    "vectorized Markdown chunks."
)

SYSTEM_PROMPT = """<role>
You are a Document Expert Agent with access to a knowledge base of ingested documents.
</role>

<objective>
Your primary mission is to answer user questions by retrieving the most relevant document
chunks using semantic search and synthesizing a coherent, accurate response.
</objective>

<context>
All documents have been pre-processed into Markdown and chunked into vector embeddings.
You can search across all documents or within a specific collection.
</context>

<tools>
[TOOLS]
</tools>

<tasks>
1. Understand the user's question.
2. Use the search tool to retrieve the most relevant document chunks.
3. Synthesize a clear, accurate answer based on the retrieved chunks.
4. Cite the source file path for each piece of information you use.
</tasks>

<operating_guidelines>
- Always use the search tool before answering — do not rely on prior knowledge alone.
- If no relevant chunks are found, say "I don't have that information in the knowledge base."
- Provide source references (file_path) for the information you use.
- Be concise and factual.
</operating_guidelines>

<constraints>
- Only use information retrieved from the document search tool.
- Do not invent facts or cite sources that were not returned by the tool.
</constraints>
"""


class DocumentSearchInput(BaseModel):
    query: str = Field(description="The natural language question or search query.")
    collection_name: str = Field(
        default="documents",
        description="The vector collection to search (default: 'documents').",
    )
    k: int = Field(
        default=5, ge=1, le=20, description="Number of top results to return."
    )


def _build_search_tool(
    embeddings_model: OpenAIEmbeddings,
    vector_store_service: Any,
) -> StructuredTool:
    """Create a LangChain StructuredTool that performs vector similarity search."""

    def search_documents(**kwargs: Any) -> List[Dict[str, Any]]:
        query: str = kwargs.get("query", "")
        collection_name: str = kwargs.get("collection_name", "documents")
        k: int = kwargs.get("k", 5)

        if not query:
            return [{"error": "query is required"}]

        try:
            query_vector = np.array(
                embeddings_model.embed_query(query), dtype=np.float32
            )
            results = vector_store_service.search_similar(
                collection_name=collection_name,
                query_vector=query_vector,
                k=k,
                include_metadata=True,
            )

            formatted: List[Dict[str, Any]] = []
            for result in results:
                meta = result.metadata or {}
                payload = result.payload or {}
                formatted.append(
                    {
                        "score": float(result.score),
                        "file_path": meta.get("file_path", "unknown"),
                        "chunk_index": meta.get("chunk_index", -1),
                        "content": payload.get("content", ""),
                    }
                )
            return formatted
        except Exception as exc:
            return [{"error": str(exc)}]

    return StructuredTool(
        name="search_documents",
        description=(
            "Search the document knowledge base using semantic similarity. "
            "Returns the most relevant text chunks with their source file paths and similarity scores."
        ),
        func=search_documents,
        args_schema=DocumentSearchInput,
    )


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> "DocumentAgent":
    from naas_abi_marketplace.ai.chatgpt.models.gpt_4_1_mini import model
    from naas_abi_marketplace.domains.document import ABIModule

    module = ABIModule.get_instance()

    embeddings_config = module.configuration.markdowntovector_pipelines[0] if module.configuration.markdowntovector_pipelines else None
    model_id = embeddings_config.model_id if embeddings_config else "text-embedding-3-small"
    dimension = embeddings_config.dimension if embeddings_config else 1536

    embeddings_model = OpenAIEmbeddings(model=model_id, dimensions=dimension)
    vector_store_service = module.engine.services.vector_store

    search_tool = _build_search_tool(embeddings_model, vector_store_service)
    tools: list[BaseTool] = [search_tool]

    system_prompt = SYSTEM_PROMPT.replace(
        "[TOOLS]",
        "\n".join(f"- {t.name}: {t.description}" for t in tools),
    )

    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=system_prompt)
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    return DocumentAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        agents=[],
        intents=[],
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class DocumentAgent(IntentAgent):
    """Agent that answers questions over ingested and vectorized documents."""

    pass
