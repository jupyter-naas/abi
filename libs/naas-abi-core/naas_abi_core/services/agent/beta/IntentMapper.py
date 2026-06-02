import threading
import weakref
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Tuple

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from naas_abi_core import logger
from naas_abi_core.engine.context import get_default_model_registry
from naas_abi_core.services.cache.CacheFactory import CacheFactory
from naas_abi_core.services.cache.CachePort import DataType

from .VectorStore import VectorStore

cache = CacheFactory.CacheFS_find_storage(subpath="intent_mapper")


def _resolve_default_embedding_model() -> Embeddings:
    """Resolve the embedding model when a caller passes ``embedding_model=None``.

    Always goes through the process-wide ``ModelRegistry``. Raises if no
    default is configured — the caller must either set
    ``services.model_registry.default_embedding_model`` in the engine config
    or pass an explicit ``embedding_model=`` argument. This intentionally
    refuses to silently instantiate a bare ``OpenAIEmbeddings()`` so that
    "where does this api key come from?" stays answerable from the config.
    """
    registry = get_default_model_registry()
    if registry is None:
        raise RuntimeError(
            "IntentMapper needs a process-wide ModelRegistry to resolve "
            "embedding_model=None — load the engine via Engine.load() first, "
            "or pass embedding_model= explicitly."
        )
    return registry.get_default_embedding_model().model


def _resolve_default_chat_model() -> BaseChatModel:
    """Resolve the chat model used by the IntentMapper's classifier when
    ``model=None``. Same policy as :func:`_resolve_default_embedding_model`."""
    registry = get_default_model_registry()
    if registry is None:
        raise RuntimeError(
            "IntentMapper needs a process-wide ModelRegistry to resolve "
            "model=None — load the engine via Engine.load() first, or pass "
            "model= explicitly."
        )
    return registry.get_default_chat_model().model


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
    embedding_workers: int

    # Weak refs to every live IntentMapper so a single helper can warm them
    # all from a background thread after API boot completes.
    _instances: "weakref.WeakSet[IntentMapper]" = weakref.WeakSet()
    _instances_lock = threading.Lock()

    def __init__(
        self,
        intents: list[Intent],
        embedding_model: Embeddings | None = None,
        model: BaseChatModel | None = None,
        embedding_workers: int = 4,
    ):
        self.intents = intents
        self._embedding_model = embedding_model or _resolve_default_embedding_model()
        self.model = model or _resolve_default_chat_model()
        self.vector_store = None
        self.embedding_workers = max(1, int(embedding_workers))

        # Lazy-index state. Embedding + Qdrant upsert used to happen here in
        # __init__; cProfile showed it cost ~280ms per agent (mostly Qdrant
        # client-side pydantic schema work) and was the dominant boot cost
        # when constructing many agents. We defer the work to the first
        # `map_intent` / `map_prompt` call. The lock guards against two
        # concurrent requests racing the first-time build. In production a
        # background warmup thread (see `warm_all`) typically builds the
        # index before any request arrives, so the latency is invisible.
        self._index_lock = threading.Lock()
        self._index_built = False

        with IntentMapper._instances_lock:
            IntentMapper._instances.add(self)

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

    @classmethod
    def warm_all_in_background(cls) -> threading.Thread:
        """Start a daemon thread that builds the vector index for every live
        IntentMapper instance. Returns the thread (for tests / instrumentation).

        Safe to call multiple times — `_ensure_index` is idempotent. If a
        chat request races the warmup, the request's call to `_ensure_index`
        will block briefly on the same lock and reuse the result.
        """

        def _warm():
            with cls._instances_lock:
                mappers = list(cls._instances)
            logger.debug(
                f"Warming intent index for {len(mappers)} IntentMapper instances "
                f"in background."
            )
            for mapper in mappers:
                try:
                    mapper._ensure_index()
                except Exception as exc:
                    logger.warning(
                        f"Background intent-index warmup failed for one mapper: {exc}"
                    )
            logger.debug("Intent index background warmup complete.")

        thread = threading.Thread(
            target=_warm, name="intent-index-warmup", daemon=True
        )
        thread.start()
        return thread

    def _ensure_index(self) -> None:
        """Build the vector index on first use. Idempotent and thread-safe."""
        if self._index_built:
            return
        with self._index_lock:
            if self._index_built:
                return

            intents_values = [intent.intent_value for intent in self.intents]
            if len(intents_values) == 0:
                self._index_built = True
                return

            if len(intents_values) <= 1 or self.embedding_workers <= 1:
                vectors = self._embed_documents(intents_values)
            else:
                batch_count = min(self.embedding_workers, len(intents_values))
                batch_size = (len(intents_values) + batch_count - 1) // batch_count
                batches: list[tuple[int, list[str]]] = [
                    (start, intents_values[start : start + batch_size])
                    for start in range(0, len(intents_values), batch_size)
                ]

                vectors_by_start: dict[int, list[list[float]]] = {}
                with ThreadPoolExecutor(max_workers=batch_count) as executor:
                    future_to_start = {
                        executor.submit(self._embed_documents, batch): start
                        for start, batch in batches
                    }
                    for future in as_completed(future_to_start):
                        start = future_to_start[future]
                        vectors_by_start[start] = future.result()

                vectors = []
                for start, _batch in batches:
                    vectors.extend(vectors_by_start[start])

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
            self._index_built = True

    def get_intent_from_value(self, value: str) -> Intent | None:
        for intent in self.intents:
            if intent.intent_value == value:
                return intent
        return None

    def _embedding_cache_namespace(self) -> str:
        model_name = getattr(self._embedding_model, "model", None)
        model_id = getattr(self._embedding_model, "model_id", None)
        return f"{type(self._embedding_model).__name__}:{model_name}:{model_id}"

    @cache(
        lambda self, texts: f"embed_documents_{self._embedding_cache_namespace()}_{texts}",
        cache_type=DataType.PICKLE,
    )
    def _embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embedding_model.embed_documents(texts)

    def _embed_query(self, text: str) -> list[float]:
        return self._embedding_model.embed_query(text)

    def map_intent(self, intent: str, k: int = 1) -> list[dict]:
        self._ensure_index()
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
