from .VectorStore import VectorStore
from .Embeddings import openai_embeddings_batch, openai_embeddings
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage
from typing import Tuple, Any, Union
from enum import Enum
from dataclasses import dataclass

class IntentType(Enum):
    AGENT = "agent"
    TOOL = "tool"
    RAW = "raw"

@dataclass
class Intent:
    intent_value: str
    intent_type: IntentType
    intent_target: Any

class IntentMapper:
    intents: list[Intent]
    vector_store: VectorStore
    model: Union[ChatOpenAI, BaseChatModel]
    system_prompt: str
    
    def __init__(self, intents: list[Intent]):
        self.intents = intents
        
        # Determine embedding dimension based on actual embeddings model
        from .Embeddings import embeddings_model
        
        # Test embedding dimension with a sample text
        test_embedding = embeddings_model.embed_query("test")
        embedding_dimension = len(test_embedding)
        
        self.vector_store = VectorStore(dimension=embedding_dimension)
        intents_values = [intent.intent_value for intent in intents]
        self.vector_store.add_texts(intents_values, embeddings=openai_embeddings_batch(intents_values))
        
        # Use local model for intent mapping if in local mode
        from src import secret
        ai_mode = secret.get("AI_MODE", "cloud")
        if ai_mode == "local":
            from src.core.gemma.models.gemma3_4b import model as local_model
            if local_model:
                self.model = local_model.model
            else:
                # Fallback to OpenAI if local model not available
                self.model = ChatOpenAI(model="gpt-4o-mini")
        else:
            self.model = ChatOpenAI(model="gpt-4o-mini")
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
        results = self.vector_store.similarity_search(openai_embeddings(intent), k=k)
        for result in results:
            result['intent'] = self.get_intent_from_value(result['text'])
    
        return results
    
    def map_prompt(self, prompt: str, k: int = 1) -> Tuple[list[dict], list[dict]]:
        response = self.model.invoke([
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=prompt)
        ])
        
        assert isinstance(response.content, str)
        intent : str = response.content.lower().strip()
        return self.map_intent(intent, k), self.map_intent(prompt, k)
