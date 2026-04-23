from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Tuple

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from naas_abi_core.utils.Logger import logger

from .VectorStore import VectorStore


class IntentScope(Enum):
    DIRECT = "direct"
    ALL = "all"


class IntentType(Enum):
    AGENT = "agent"
    TOOL = "tool"
    RAW = "raw"


@dataclass
class Intent:
    intent_value: str
    intent_type: IntentType
    intent_target: Any
    intent_scope: Optional[IntentScope] = IntentScope.ALL


class IntentMapper:
    intents: list[Intent]
    vector_store: VectorStore | None
    _embedding_model: Embeddings
    model: BaseChatModel
    system_prompt: str

    def __init__(
        self,
        intents: list[Intent],
        embedding_model: Embeddings | None = None,
        model: BaseChatModel | None = None,
    ):
        self.intents = intents
        self._embedding_model = embedding_model or OpenAIEmbeddings(
            model="text-embedding-3-large"
        )
        self.model = model or ChatOpenAI(model="gpt-4.1-mini")
        self.vector_store = None

        if embedding_model is None:
            logger.warning(
                "No embedding_model provided to IntentMapper; using default OpenAIEmbeddings "
                "model='text-embedding-3-large'."
            )
        if model is None:
            logger.warning(
                "No model provided to IntentMapper; using default ChatOpenAI model='gpt-4.1-mini'."
            )

        intents_values = [intent.intent_value for intent in intents]
        if len(intents_values) > 0:
            vectors = self._embed_documents(intents_values)
            if len(vectors) == 0 or len(vectors[0]) == 0:
                raise ValueError(
                    "Unable to build intent index: empty embedding vectors"
                )

            self.vector_store = VectorStore(dimension=len(vectors[0]))
            metadatas = [{"index": index} for index in range(len(intents_values))]
            self.vector_store.add_texts(
                intents_values,
                embeddings=vectors,
                metadatas=metadatas,
            )

        # Set the system prompt
        self.system_prompt = """
You are an intent mapper. The user will send you a prompt and you should output the intent and the intent only. If the user references a technology, you must have the name of the technology in the intent.

Example:
User: 3 / 4 + 5
You: calculate an arithmetic result

User: I need to write a report about the latest trends in AI.
You: write a report

User: I need to code a project.
You: code a project
"""

    def get_intent_from_value(self, value: str) -> Intent | None:
        for intent in self.intents:
            if intent.intent_value == value:
                return intent
        return None

    def _embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embedding_model.embed_documents(texts)

    def _embed_query(self, text: str) -> list[float]:
        return self._embedding_model.embed_query(text)

    def map_intent(self, intent: str, k: int = 1) -> list[dict]:
        if self.vector_store is None:
            return []

        results = self.vector_store.similarity_search(self._embed_query(intent), k=k)
        for result in results:
            result["intent"] = self.intents[result["metadata"]["index"]]

        return results

    def map_prompt(self, prompt: str, k: int = 1) -> Tuple[list[dict], list[dict]]:
        # Use direct prompt mapping without LLM intent extraction for speed
        # Return empty first result and prompt results as second (matches expected format)
        prompt_results = self.map_intent(prompt, k)
        return [], prompt_results
