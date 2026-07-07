from datetime import datetime
from enum import Enum, StrEnum
from typing import Annotated, Optional, Union

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import Field


class ModelType(Enum):
    CHAT = "chat"
    EMBEDDING = "embedding"


class ModelProvider(StrEnum):
    """Well-known providers. Registry calls accept either this enum or a raw string."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    BEDROCK = "bedrock"
    OLLAMA = "ollama"
    MISTRAL = "mistral"
    META = "meta"
    XAI = "xai"
    PERPLEXITY = "perplexity"
    OPENROUTER = "openrouter"
    ALIBABA = "alibaba"
    QWEN = "qwen"


class CanonicalModelId(StrEnum):
    """Well-known canonical model identifiers used by ABI across providers.

    The registry accepts this enum or any raw string; modules contribute the
    actual (canonical_id, provider, provider_model_id) mappings at load time.
    """

    # Chat — Anthropic family
    CLAUDE_SONNET_5 = "claude-sonnet-5"
    CLAUDE_SONNET_4_6 = "claude-sonnet-4.6"
    CLAUDE_SONNET_4_5 = "claude-sonnet-4.5"
    CLAUDE_SONNET_4 = "claude-sonnet-4"
    CLAUDE_SONNET_3_7 = "claude-sonnet-3.7"
    CLAUDE_OPUS_4_7 = "claude-opus-4.7"
    CLAUDE_OPUS_4_1 = "claude-opus-4.1"
    CLAUDE_OPUS_4 = "claude-opus-4"
    CLAUDE_HAIKU_4_5 = "claude-haiku-4.5"
    CLAUDE_HAIKU_3_5 = "claude-haiku-3.5"

    # Chat — Meta family
    LLAMA_3_3_70B = "llama-3.3-70b"

    # Chat — Amazon family
    NOVA_PRO = "nova-pro"

    # Embedding — Amazon family
    TITAN_EMBED_TEXT_V2 = "titan-embed-text-v2"

    # Embedding — OpenAI family
    TEXT_EMBEDDING_3_LARGE = "text-embedding-3-large"
    TEXT_EMBEDDING_3_SMALL = "text-embedding-3-small"
    TEXT_EMBEDDING_ADA_002 = "text-embedding-ada-002"

    # Chat — OpenAI family
    GPT_5 = "gpt-5"
    GPT_5_MINI = "gpt-5-mini"
    GPT_5_NANO = "gpt-5-nano"
    GPT_5_1 = "gpt-5.1"
    GPT_5_1_MINI = "gpt-5.1-mini"
    GPT_5_5 = "gpt-5.5"
    GPT_5_3_CODEX = "gpt-5.3-codex"
    GPT_5_2 = "gpt-5.2"
    GPT_4_1 = "gpt-4.1"
    GPT_4_1_MINI = "gpt-4.1-mini"
    GPT_4O = "gpt-4o"
    O3_MINI = "o3-mini"
    O3_DEEP_RESEARCH = "o3-deep-research"
    O4_MINI_DEEP_RESEARCH = "o4-mini-deep-research"

    # Chat — Google family
    GEMINI_3_1_PRO_PREVIEW = "gemini-3.1-pro-preview"
    GEMINI_2_5_FLASH = "gemini-2.5-flash"
    GEMINI_2_5_PRO = "gemini-2.5-pro"
    GEMMA_3_27B_IT = "gemma-3-27b-it"

    # Chat — xAI family
    GROK_4_1_FAST = "grok-4.1-fast"
    GROK_4 = "grok-4"

    # Chat — DeepSeek family
    DEEPSEEK_V3_2 = "deepseek-v3.2"

    # Chat — Mistral family
    MISTRAL_LARGE_2512 = "mistral-large-2512"
    MISTRAL_LARGE_2407 = "mistral-large-2407"
    MISTRAL_LARGE = "mistral-large"
    MISTRAL_MEDIUM_3 = "mistral-medium-3"
    MISTRAL_MEDIUM_3_1 = "mistral-medium-3.1"
    MISTRAL_MEDIUM_3_5 = "mistral-medium-3-5"
    MISTRAL_SMALL_24B_INSTRUCT_2501 = "mistral-small-24b-instruct-2501"
    MISTRAL_SMALL_2603 = "mistral-small-2603"
    MISTRAL_SMALL_3_1_24B_INSTRUCT = "mistral-small-3.1-24b-instruct"
    MISTRAL_SMALL_3_2_24B_INSTRUCT = "mistral-small-3.2-24b-instruct"
    MISTRAL_NEMO = "mistral-nemo"
    MISTRAL_SABA = "mistral-saba"
    MINISTRAL_3B_2512 = "ministral-3b-2512"
    MINISTRAL_8B_2512 = "ministral-8b-2512"
    MINISTRAL_14B_2512 = "ministral-14b-2512"
    MIXTRAL_8X22B_INSTRUCT = "mixtral-8x22b-instruct"
    CODESTRAL_2508 = "codestral-2508"
    DEVSTRAL_2512 = "devstral-2512"
    VOXTRAL_SMALL_24B_2507 = "voxtral-small-24b-2507"

    # Chat — Perplexity family
    SONAR_PRO_SEARCH = "sonar-pro-search"

    # Chat — OpenAI open-weights
    GPT_OSS_120B = "gpt-oss-120b"
    GPT_OSS_120B_FREE = "gpt-oss-120b:free"
    GPT_OSS_20B = "gpt-oss-20b"
    GPT_OSS_20B_FREE = "gpt-oss-20b:free"
    GPT_OSS_SAFEGUARD_20B = "gpt-oss-safeguard-20b"

    # Chat - Qwen family
    QWEN_3_6 = "qwen-3.6"

    # Chat — Anthropic (extended family)
    CLAUDE_FABLE_5 = "claude-fable-5"
    CLAUDE_OPUS_4_5 = "claude-opus-4.5"
    CLAUDE_OPUS_4_6 = "claude-opus-4.6"
    CLAUDE_OPUS_4_6_FAST = "claude-opus-4.6-fast"
    CLAUDE_OPUS_4_7_FAST = "claude-opus-4.7-fast"
    CLAUDE_OPUS_4_8 = "claude-opus-4.8"
    CLAUDE_OPUS_4_8_FAST = "claude-opus-4.8-fast"
    CLAUDE_3_5_HAIKU = "claude-3.5-haiku"
    CLAUDE_3_HAIKU = "claude-3-haiku"

    # Chat — OpenAI (extended family)
    GPT_CHAT_LATEST = "gpt-chat-latest"
    GPT_5_PRO = "gpt-5-pro"
    GPT_5_CODEX = "gpt-5-codex"
    GPT_5_CHAT = "gpt-5-chat"
    GPT_5_IMAGE = "gpt-5-image"
    GPT_5_IMAGE_MINI = "gpt-5-image-mini"
    GPT_5_5_PRO = "gpt-5.5-pro"
    GPT_5_4 = "gpt-5.4"
    GPT_5_4_PRO = "gpt-5.4-pro"
    GPT_5_4_MINI = "gpt-5.4-mini"
    GPT_5_4_NANO = "gpt-5.4-nano"
    GPT_5_4_IMAGE_2 = "gpt-5.4-image-2"
    GPT_5_3_CHAT = "gpt-5.3-chat"
    GPT_5_2_PRO = "gpt-5.2-pro"
    GPT_5_2_CHAT = "gpt-5.2-chat"
    GPT_5_2_CODEX = "gpt-5.2-codex"
    GPT_5_1_CHAT = "gpt-5.1-chat"
    GPT_5_1_CODEX = "gpt-5.1-codex"
    GPT_5_1_CODEX_MAX = "gpt-5.1-codex-max"
    GPT_5_1_CODEX_MINI = "gpt-5.1-codex-mini"
    GPT_4_1_NANO = "gpt-4.1-nano"
    GPT_4_TURBO = "gpt-4-turbo"
    GPT_4_TURBO_PREVIEW = "gpt-4-turbo-preview"
    GPT_4 = "gpt-4"
    GPT_4O_2024_11_20 = "gpt-4o-2024-11-20"
    GPT_4O_2024_08_06 = "gpt-4o-2024-08-06"
    GPT_4O_2024_05_13 = "gpt-4o-2024-05-13"
    GPT_4O_MINI = "gpt-4o-mini"
    GPT_4O_MINI_2024_07_18 = "gpt-4o-mini-2024-07-18"
    GPT_4O_SEARCH_PREVIEW = "gpt-4o-search-preview"
    GPT_4O_MINI_SEARCH_PREVIEW = "gpt-4o-mini-search-preview"
    GPT_AUDIO = "gpt-audio"
    GPT_AUDIO_MINI = "gpt-audio-mini"
    GPT_3_5_TURBO = "gpt-3.5-turbo"
    GPT_3_5_TURBO_0613 = "gpt-3.5-turbo-0613"
    GPT_3_5_TURBO_16K = "gpt-3.5-turbo-16k"
    GPT_3_5_TURBO_INSTRUCT = "gpt-3.5-turbo-instruct"
    O1 = "o1"
    O1_PRO = "o1-pro"
    O3 = "o3"
    O3_PRO = "o3-pro"
    O3_MINI_HIGH = "o3-mini-high"
    O4_MINI = "o4-mini"
    O4_MINI_HIGH = "o4-mini-high"

    # Chat — Nvidia family
    NEMOTRON_3_5_CONTENT_SAFETY_FREE = "nemotron-3.5-content-safety:free"
    NEMOTRON_3_ULTRA_550B_A55B = "nemotron-3-ultra-550b-a55b"
    NEMOTRON_3_ULTRA_550B_A55B_FREE = "nemotron-3-ultra-550b-a55b:free"
    NEMOTRON_3_SUPER_120B_A12B = "nemotron-3-super-120b-a12b"
    NEMOTRON_3_SUPER_120B_A12B_FREE = "nemotron-3-super-120b-a12b:free"
    NEMOTRON_3_NANO_30B_A3B = "nemotron-3-nano-30b-a3b"
    NEMOTRON_3_NANO_30B_A3B_FREE = "nemotron-3-nano-30b-a3b:free"
    NEMOTRON_3_NANO_OMNI_30B_A3B_REASONING_FREE = "nemotron-3-nano-omni-30b-a3b-reasoning:free"
    NEMOTRON_NANO_9B_V2 = "nemotron-nano-9b-v2"
    NEMOTRON_NANO_9B_V2_FREE = "nemotron-nano-9b-v2:free"
    NEMOTRON_NANO_12B_V2_VL_FREE = "nemotron-nano-12b-v2-vl:free"
    LLAMA_3_3_NEMOTRON_SUPER_49B_V1_5 = "llama-3.3-nemotron-super-49b-v1.5"


# Type aliases for registry call sites — accept enum or raw string.
CanonicalModelIdLike = Union[CanonicalModelId, str]
ModelProviderLike = Union[ModelProvider, str]


class ModelDefinition:
    """Declarative marker for files under ``<module>/models/``.

    Each model file under a module's ``models/`` directory should define
    exactly one subclass of ``ModelDefinition`` whose body sets:

    * ``CANONICAL_ID`` — a :class:`CanonicalModelId` or raw string.
    * ``model`` — a :class:`Model` (typically :class:`ChatModel` or
      :class:`EmbeddingModel`) instance.

    ``MODEL_ID`` and ``PROVIDER`` are not required by the loader (the
    ``provider`` and provider-specific ``model_id`` live on the ``Model``
    instance itself), but defining them as class attributes is the
    idiomatic shape — they make the file self-documenting and let the
    ``model`` assignment reference them locally.

    Example::

        class GptFourOneMini(ModelDefinition):
            CANONICAL_ID = CanonicalModelId.GPT_4_1_MINI
            MODEL_ID = "gpt-4.1-mini"
            PROVIDER = ModelProvider.OPENAI

            model: ChatModel = ChatModel(
                model_id=MODEL_ID,
                provider=PROVIDER,
                model=ChatOpenAI(model=MODEL_ID, ...),
            )

    The :class:`ModuleModelLoader` finds every ``ModelDefinition`` subclass
    defined in the module's ``models/`` directory and calls
    ``registry.register(CANONICAL_ID, model)`` for each one.
    """

    CANONICAL_ID: CanonicalModelIdLike
    model: "Model"


class Model:
    model_id: Annotated[str, Field(description="Provider-specific model identifier")]
    provider: Annotated[
        str,
        Field(
            description="The provider of the model (e.g. 'openai', 'anthropic', 'openrouter', 'aws bedrock', etc.)"
        ),
    ]
    model: Annotated[
        BaseChatModel, Field(description="The base model chat from Langchain")
    ]
    name: Annotated[
        Optional[str],
        Field(
            description="Display name of the model (e.g. 'GPT-4.1', 'Claude Sonnet 4.5', 'Grok 4', 'Mistral Large', 'Gemini 2.5 Flash', etc.)"
        ),
    ]
    owner: Annotated[Optional[str], Field(description="The owner/creator of the model")]
    description: Annotated[
        Optional[str],
        Field(
            description="The description of the model (e.g. 'GPT-4.1 is OpenAI's most advanced model with superior performance across text, code, and reasoning tasks.', 'Claude Sonnet 4.5 is Anthropic's most advanced Sonnet model to date, optimized for real-world agents and coding workflows.', 'Grok 4 is xAI's latest multimodal model with SOTA cost-efficiency and a 2M token context window. It comes in two flavors: non-reasoning and reasoning. Read more about the model on xAI's [news post](http://x.ai/news/grok-4-fast). Reasoning can be enabled using the `reasoning` `enabled` parameter in the API. [Learn more in our docs](https://openrouter.ai/docs/use-cases/reasoning-tokens#controlling-reasoning-tokens)', 'Mistral Large is Mistral's latest large model with superior performance across text, code, and reasoning tasks.', 'Gemini 2.5 Flash is Google's latest multimodal model with superior performance across text, code, and reasoning tasks.', etc.)"
        ),
    ]
    image: Annotated[Optional[str], Field(description="The image of the model")]
    created_at: Annotated[
        Optional[datetime], Field(description="The date and time the model was created")
    ]
    canonical_slug: Annotated[
        Optional[str], Field(description="Canonical slug for the model")
    ]
    hugging_face_id: Annotated[
        Optional[str], Field(description="Hugging Face model identifier, if applicable")
    ]
    pricing: Annotated[
        Optional[dict], Field(description="Pricing information for the model")
    ]
    architecture: Annotated[
        Optional[dict], Field(description="Model architecture information")
    ]
    top_provider: Annotated[
        Optional[dict],
        Field(description="Information about the top provider for this model"),
    ]
    per_request_limits: Annotated[
        Optional[dict], Field(description="Per-request token limits")
    ]
    supported_parameters: Annotated[
        Optional[list], Field(description="List of supported parameters for this model")
    ]
    default_parameters: Annotated[
        Optional[dict], Field(description="Default parameters for this model")
    ]

    def __init__(
        self,
        model_id: str,
        provider: str,
        model: BaseChatModel,
        name: Optional[str] = None,
        owner: Optional[str] = None,
        description: Optional[str] = None,
        image: Optional[str] = None,
        created_at: Optional[datetime] = None,
        canonical_slug: Optional[str] = None,
        hugging_face_id: Optional[str] = None,
        pricing: Optional[dict] = None,
        architecture: Optional[dict] = None,
        top_provider: Optional[dict] = None,
        per_request_limits: Optional[dict] = None,
        supported_parameters: Optional[list] = None,
        default_parameters: Optional[dict] = None,
    ):
        self.model_id = model_id
        self.provider = provider
        self.model = model
        self.name = name
        self.owner = owner
        self.description = description
        self.image = image
        self.created_at = created_at
        self.canonical_slug = canonical_slug
        self.hugging_face_id = hugging_face_id
        self.pricing = pricing
        self.architecture = architecture
        self.top_provider = top_provider
        self.per_request_limits = per_request_limits
        self.supported_parameters = supported_parameters
        self.default_parameters = default_parameters


class ChatModel(Model):
    model: BaseChatModel
    context_window: Annotated[
        Optional[int], Field(description="Maximum context length in tokens")
    ]
    model_type: ModelType = ModelType.CHAT

    def __init__(
        self,
        model_id: str,
        provider: str,
        model: BaseChatModel,
        context_window: Optional[int] = None,
        name: Optional[str] = None,
        owner: Optional[str] = None,
        description: Optional[str] = None,
        image: Optional[str] = None,
        created_at: Optional[datetime] = None,
        canonical_slug: Optional[str] = None,
        hugging_face_id: Optional[str] = None,
        pricing: Optional[dict] = None,
        architecture: Optional[dict] = None,
        top_provider: Optional[dict] = None,
        per_request_limits: Optional[dict] = None,
        supported_parameters: Optional[list] = None,
        default_parameters: Optional[dict] = None,
    ):
        super().__init__(
            model_id=model_id,
            provider=provider,
            model=model,
            name=name,
            owner=owner,
            description=description,
            image=image,
            created_at=created_at,
            canonical_slug=canonical_slug,
            hugging_face_id=hugging_face_id,
            pricing=pricing,
            architecture=architecture,
            top_provider=top_provider,
            per_request_limits=per_request_limits,
            supported_parameters=supported_parameters,
            default_parameters=default_parameters,
        )
        self.model_type = ModelType.CHAT
        self.context_window = context_window


class EmbeddingModel(Model):
    """Embedding model — wraps a LangChain ``Embeddings`` implementation."""

    model: Embeddings  # type: ignore[assignment]
    dimensions: Annotated[
        Optional[int],
        Field(description="Output embedding dimensionality, if known"),
    ]
    model_type: ModelType = ModelType.EMBEDDING

    def __init__(
        self,
        model_id: str,
        provider: str,
        model: Embeddings,
        dimensions: Optional[int] = None,
        name: Optional[str] = None,
        owner: Optional[str] = None,
        description: Optional[str] = None,
        image: Optional[str] = None,
        created_at: Optional[datetime] = None,
        canonical_slug: Optional[str] = None,
        hugging_face_id: Optional[str] = None,
        pricing: Optional[dict] = None,
        architecture: Optional[dict] = None,
        top_provider: Optional[dict] = None,
        per_request_limits: Optional[dict] = None,
        supported_parameters: Optional[list] = None,
        default_parameters: Optional[dict] = None,
    ):
        # Bypass parent's typed-as-BaseChatModel attribute assignment by
        # initializing fields directly — Embeddings is not a BaseChatModel.
        self.model_id = model_id
        self.provider = provider
        self.model = model  # type: ignore[assignment]
        self.name = name
        self.owner = owner
        self.description = description
        self.image = image
        self.created_at = created_at
        self.canonical_slug = canonical_slug
        self.hugging_face_id = hugging_face_id
        self.pricing = pricing
        self.architecture = architecture
        self.top_provider = top_provider
        self.per_request_limits = per_request_limits
        self.supported_parameters = supported_parameters
        self.default_parameters = default_parameters
        self.dimensions = dimensions
        self.model_type = ModelType.EMBEDDING
