"""DocumentAgent — an agent that can talk over all ingested and vectorized documents.

It exposes a hybrid search tool that combines:
- semantic search over the vector store collection
- keyword (text) search over the chunk contents stored in the triple store

Keyword matching is case-insensitive and accent-insensitive (NFKD normalization),
so French queries like ``"épée"`` and ``"Epee"`` match the same chunks.
"""

from __future__ import annotations

import unicodedata
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
    "Answers questions about ingested documents by performing semantic + keyword "
    "search over vectorized Markdown chunks."
)

DEFAULT_GRAPH_NAME = "http://ontology.naas.ai/graph/document"

SYSTEM_PROMPT = """<role>
You are a Document Expert Agent with access to a knowledge base of ingested documents.
</role>

<objective>
Your primary mission is to answer user questions by retrieving the most relevant document
chunks using a combination of semantic search and keyword (text) search, then synthesizing
a coherent, accurate response.
</objective>

<context>
All documents have been pre-processed into Markdown and chunked. Each chunk is:
- embedded into a vector store for semantic search, and
- stored as text in the triple store for keyword search.

You can search across all documents or within a specific collection. The search tool accepts
both a natural language ``query`` (for semantic search) and an optional list of ``keywords``
that must ALL appear in the chunk content (case-insensitive, accent-insensitive — so
``"epee"`` matches ``"épée"``).
</context>

<tools>
[TOOLS]
</tools>

<tasks>
1. Understand the user's question.
2. Use the search tool to retrieve the most relevant document chunks. Provide ``keywords``
   when the user mentions specific terms, names, or identifiers that must appear verbatim.
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
    query: str = Field(
        default="",
        description="The natural language question for semantic similarity search.",
    )
    keywords: List[str] = Field(
        default_factory=list,
        description=(
            "Optional list of text terms that must ALL appear in a chunk's content. "
            "Matching is case-insensitive and accent-insensitive."
        ),
    )
    collection_name: str = Field(
        default="documents",
        description="The vector collection to search (default: 'documents').",
    )
    k: int = Field(
        default=5, ge=1, le=20, description="Number of top results to return per search mode."
    )


def _normalize_text(text: str) -> str:
    """Lowercase ``text`` and strip combining marks (accents).

    Uses NFKD normalization so ``"Épée"`` → ``"epee"``. Works for the
    Latin-script accents typically found in French, Spanish, etc.
    """
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return stripped.lower()


def _result_key(file_path: str, chunk_index: Any) -> tuple:
    return (file_path, chunk_index)


def _vector_search(
    *,
    query: str,
    collection_name: str,
    k: int,
    embeddings_model: OpenAIEmbeddings,
    vector_store_service: Any,
    keywords_normalized: List[str],
) -> List[Dict[str, Any]]:
    query_vector = np.array(embeddings_model.embed_query(query), dtype=np.float32)
    # When keywords are also provided, fetch a wider net so we can intersect
    # them with the keyword constraint without starving the result set.
    fetch_k = k * 4 if keywords_normalized else k
    results = vector_store_service.search_similar(
        collection_name=collection_name,
        query_vector=query_vector,
        k=fetch_k,
        include_metadata=True,
    )

    formatted: List[Dict[str, Any]] = []
    for result in results:
        meta = result.metadata or {}
        payload = result.payload or {}
        content = payload.get("content", "")

        if keywords_normalized:
            normalized = _normalize_text(content)
            if not all(kw in normalized for kw in keywords_normalized):
                continue

        formatted.append(
            {
                "score": float(result.score),
                "file_path": meta.get("file_path", "unknown"),
                "chunk_index": meta.get("chunk_index", -1),
                "content": content,
                "match_type": "vector",
            }
        )
        if len(formatted) >= k:
            break
    return formatted


def _keyword_search(
    *,
    keywords_normalized: List[str],
    collection_name: str,
    k: int,
    triple_store_service: Any,
    graph_name: str,
) -> List[Dict[str, Any]]:
    """Pull chunk contents from the triple store and return those that match
    *all* normalized keywords.
    """
    # Pull every chunk's (file_path, index, content) for this collection.
    # Filtering happens in Python so we get proper Unicode case + accent folding.
    safe_collection = collection_name.replace('"', '\\"')
    query = f"""
    PREFIX doc: <http://ontology.naas.ai/abi/document/>
    SELECT ?file_path ?chunk_index ?content WHERE {{
        GRAPH <{graph_name}> {{
            ?chunk a doc:Chunk ;
                   doc:file_path ?file_path ;
                   doc:chunk_index ?chunk_index ;
                   doc:content ?content ;
                   doc:collection_name "{safe_collection}" .
        }}
    }}
    """
    rows = triple_store_service.query(query)

    matches: List[Dict[str, Any]] = []
    for row in rows:
        try:
            if hasattr(row, "file_path"):
                file_path = str(getattr(row, "file_path"))
                chunk_index_raw = getattr(row, "chunk_index")
                content = str(getattr(row, "content"))
            else:
                file_path = str(row["file_path"])  # type: ignore[index]
                chunk_index_raw = row["chunk_index"]  # type: ignore[index]
                content = str(row["content"])  # type: ignore[index]
        except Exception:
            continue

        try:
            chunk_index: Any = int(str(chunk_index_raw))
        except (TypeError, ValueError):
            chunk_index = str(chunk_index_raw)

        normalized = _normalize_text(content)
        if not all(kw in normalized for kw in keywords_normalized):
            continue

        matches.append(
            {
                "score": 1.0,
                "file_path": file_path,
                "chunk_index": chunk_index,
                "content": content,
                "match_type": "keyword",
            }
        )
        if len(matches) >= k:
            break
    return matches


def _build_search_tool(
    embeddings_model: OpenAIEmbeddings,
    vector_store_service: Any,
    triple_store_service: Optional[Any] = None,
    graph_name: str = DEFAULT_GRAPH_NAME,
) -> StructuredTool:
    """Create a LangChain StructuredTool that performs hybrid search.

    The tool returns the union of:
    - vector similarity results for ``query`` (filtered by ``keywords`` when both
      are provided), and
    - chunks whose content contains every entry in ``keywords`` (normalized).
    """

    def search_documents(**kwargs: Any) -> List[Dict[str, Any]]:
        query: str = (kwargs.get("query") or "").strip()
        raw_keywords = kwargs.get("keywords") or []
        collection_name: str = kwargs.get("collection_name", "documents")
        k: int = kwargs.get("k", 5)

        keywords_normalized = [
            _normalize_text(str(kw)) for kw in raw_keywords if str(kw).strip()
        ]

        if not query and not keywords_normalized:
            return [{"error": "query or keywords is required"}]

        combined: List[Dict[str, Any]] = []
        seen: set = set()

        try:
            if query:
                for hit in _vector_search(
                    query=query,
                    collection_name=collection_name,
                    k=k,
                    embeddings_model=embeddings_model,
                    vector_store_service=vector_store_service,
                    keywords_normalized=keywords_normalized,
                ):
                    key = _result_key(hit["file_path"], hit["chunk_index"])
                    if key in seen:
                        continue
                    seen.add(key)
                    combined.append(hit)

            if keywords_normalized and triple_store_service is not None:
                for hit in _keyword_search(
                    keywords_normalized=keywords_normalized,
                    collection_name=collection_name,
                    k=k,
                    triple_store_service=triple_store_service,
                    graph_name=graph_name,
                ):
                    key = _result_key(hit["file_path"], hit["chunk_index"])
                    if key in seen:
                        continue
                    seen.add(key)
                    combined.append(hit)

            return combined
        except Exception as exc:
            return [{"error": str(exc)}]

    return StructuredTool(
        name="search_documents",
        description=(
            "Search the document knowledge base. Supply a natural-language ``query`` "
            "for semantic similarity and/or a list of ``keywords`` (case-insensitive, "
            "accent-insensitive) that must ALL appear in the chunk content. Returns "
            "the relevant text chunks with their source file paths and scores."
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

    agent_config = module.configuration.document_agent

    embeddings_model = OpenAIEmbeddings(
        model=agent_config.model_id,
        dimensions=agent_config.dimension,
        api_key=agent_config.api_key,
    )
    vector_store_service = module.engine.services.vector_store
    triple_store_service = module.engine.services.triple_store

    search_tool = _build_search_tool(
        embeddings_model,
        vector_store_service,
        triple_store_service=triple_store_service,
    )
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

    name: str = NAME
    pass
