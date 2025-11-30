import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Tuple

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from .Embeddings import EMBEDDINGS_MODELS_DIMENSIONS_MAP, embeddings_batch
from .Embeddings import _model_name as embeddings_model_name
from .Embeddings import embeddings as embeddings
from .VectorStore import VectorStore

load_dotenv()


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
    vector_store: VectorStore
    model: ChatOpenAI
    system_prompt: str

    def __init__(self, intents: list[Intent]):
        self.intents = intents

        # Use environment-based detection for consistent embedding source
        if embeddings_model_name is not None:
            dimension: int = EMBEDDINGS_MODELS_DIMENSIONS_MAP.get(
                embeddings_model_name, 1536
            )
        else:
            raise ValueError("Embeddings model name is not set")

        self.vector_store = VectorStore(dimension=dimension)
        intents_values = [intent.intent_value for intent in intents]
        metadatas = [{"index": index} for index in range(len(intents_values))]
        self.vector_store.add_texts(
            intents_values,
            embeddings=embeddings_batch(intents_values),
            metadatas=metadatas,
        )

        api_key_value = os.getenv("OPENROUTER_API_KEY")
        api_key = SecretStr(api_key_value) if api_key_value else None

        # Detect if we're using local embeddings (768 dim = airgap mode)
        if os.getenv("AI_MODE") == "airgap":
            from naas_abi_core.services.agent.beta.LocalModel import AirgapChatOpenAI

            self.model = AirgapChatOpenAI(
                model="ai/gemma3",
                temperature=0.7,
                base_url="http://localhost:12434/engines/v1",
                api_key="ignored",
            )
        # Detect if we're using OpenRouter
        elif api_key:
            self.model = ChatOpenAI(
                model="gpt-4.1-mini",
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1",
            )
        # Fallback to OpenAI
        else:
            self.model = ChatOpenAI(model="gpt-4.1-mini")

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

    def map_intent(self, intent: str, k: int = 1) -> list[dict]:
        results = self.vector_store.similarity_search(embeddings(intent), k=k)
        for result in results:
            result["intent"] = self.intents[result["metadata"]["index"]]

        return results

    def map_prompt(self, prompt: str, k: int = 1) -> Tuple[list[dict], list[dict]]:
        # Use direct prompt mapping without LLM intent extraction for speed
        # Return empty first result and prompt results as second (matches expected format)
        prompt_results = self.map_intent(prompt, k)
        return [], prompt_results
