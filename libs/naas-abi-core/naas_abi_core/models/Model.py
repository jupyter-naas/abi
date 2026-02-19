from datetime import datetime
from enum import Enum
from typing import Annotated, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import Field


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
