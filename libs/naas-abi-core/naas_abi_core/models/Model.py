import os
from datetime import datetime
from enum import Enum
from typing import Annotated, Dict, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from naas_abi_core.models.OpenRouter import ChatOpenRouter
from pydantic import Field

OPENROUTER_MODEL_MAPPING: Dict[str, str] = {
    "gpt-5": "openai/gpt-5",
    "gpt-5-mini": "openai/gpt-5-mini",
    "gpt-5-nano": "openai/gpt-5-nano",
    "gpt-4.1": "openai/gpt-4.1",
    "gpt-4.1-mini": "openai/gpt-4.1-mini",
    "o3-deep-research": "openai/o3-deep-research",
    "o4-mini-deep-research": "openai/o4-mini-deep-research",
    "o3-mini": "openai/o3-mini",
    "sonar-pro-search": "perplexity/sonar-pro-search",
    "sonar-reasoning-pro": "perplexity/sonar-reasoning-pro",
    "sonar-pro": "perplexity/sonar-pro",
    "sonar-deep-research": "perplexity/sonar-deep-research",
    "sonar-reasoning": "perplexity/sonar-reasoning",
    "sonar": "perplexity/sonar",
    "claude-haiku-4-5-20251001": "anthropic/claude-haiku-4.5",
    "claude-sonnet-4-5-20250929": "anthropic/claude-sonnet-4.5",
    "claude-opus-4-1-20250805": "anthropic/claude-opus-4.1",
    "claude-opus-4-20250514": "anthropic/claude-opus-4",
    "claude-sonnet-4-20250514": "anthropic/claude-sonnet-4",
    "claude-3-7-sonnet-20250219": "anthropic/claude-3.7-sonnet",
    "qwen3:8b": "qwen/qwen3-8b",
    "mistral-large-2411": "mistralai/mistral-large-2411",
    "mistral-medium-2508": "mistralai/mistral-medium-3.1",
    "mistral-small-2506": "mistralai/mistral-small",
    "grok-4": "x-ai/grok-4",
    "gemini-2.5-flash": "google/gemini-2.5-flash",
}


class ModelType(Enum):
    CHAT = "chat"


class Model:
    model_id: Annotated[str, Field(description="Unique identifier for the model")]
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

        # If OPENROUTER_API_KEY is set, use ChatOpenRouter as BaseChatModel
        if (
            os.getenv("OPENROUTER_API_KEY")
            and os.getenv("AI_MODE") == "cloud"
            and isinstance(model, BaseChatModel)
            and not isinstance(model, ChatOpenRouter)
        ):
            if model_id in OPENROUTER_MODEL_MAPPING:
                self.model = ChatOpenRouter(
                    model_name=OPENROUTER_MODEL_MAPPING[model_id]
                )
            else:
                raise ValueError(f"""Model '{model_id}' from provider '{provider}' not found in OPENROUTER_MODEL_MAPPING. 
                Please add it to the mapping in lib/abi/models/Model.py.""")
        else:
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
