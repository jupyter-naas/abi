from .VectorStore import VectorStore
from .Embeddings import openai_embeddings_batch, openai_embeddings
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from typing import Tuple, Any, Optional
from enum import Enum
from dataclasses import dataclass
import os

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
    vector_store: Optional[VectorStore]
    model: Optional[ChatOpenAI]
    system_prompt: str
    _embeddings_available: bool
    
    def __init__(self, intents: list[Intent]):
        self.intents = intents
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
        
        # Initialize embeddings and vector store - now works with HuggingFace by default
        self._embeddings_available = True  # HuggingFace is always available
        
        try:
            # Use 384 dimensions for HuggingFace embeddings (all-MiniLM-L6-v2)
            self.vector_store = VectorStore(dimension=384)
            intents_values = [intent.intent_value for intent in intents]
            self.vector_store.add_texts(intents_values, embeddings=openai_embeddings_batch(intents_values))
            
            # Initialize LLM only if OpenAI API key is available
            if os.getenv("OPENAI_API_KEY"):
                self.model = ChatOpenAI(model="gpt-4o-mini")
            else:
                self.model = None
        except Exception as e:
            print(f"Warning: Failed to initialize embeddings/LLM components: {e}")
            self._embeddings_available = False
            self.vector_store = None
            self.model = None
    
    def get_intent_from_value(self, value: str) -> Intent | None:
        for intent in self.intents:
            if intent.intent_value == value:
                return intent
        return None
    
    def map_intent(self, intent: str, k: int = 1) -> list[dict]:
        if not self._embeddings_available or not self.vector_store:
            # Fallback: return exact matches only
            exact_matches = []
            for intent_obj in self.intents:
                if intent.lower() in intent_obj.intent_value.lower():
                    exact_matches.append({
                        'text': intent_obj.intent_value,
                        'intent': intent_obj,
                        'score': 1.0
                    })
            return exact_matches[:k]
        
        results = self.vector_store.similarity_search(openai_embeddings(intent), k=k)
        for result in results:
            result['intent'] = self.get_intent_from_value(result['text'])
    
        return results
    
    def map_prompt(self, prompt: str, k: int = 1) -> Tuple[list[dict], list[dict]]:
        if not self._embeddings_available or not self.model:
            # Fallback: use simple keyword matching
            fallback_intent = prompt.lower().strip()
            return self.map_intent(fallback_intent, k), self.map_intent(prompt, k)
        
        response = self.model.invoke([
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=prompt)
        ])
        
        assert isinstance(response.content, str)
        mapped_intent : str = response.content.lower().strip()
        return self.map_intent(mapped_intent, k), self.map_intent(prompt, k)
