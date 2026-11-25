from datetime import datetime

from langchain_openai import ChatOpenAI
from naas_abi_core.models.Model import (
    ChatModel,
    ModelDefinition,
    ModelProvider,
)
from naas_abi_marketplace.ai.openrouter import ABIModule
from pydantic import SecretStr

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class SonarModel(ModelDefinition):
    CANONICAL_ID = "sonar"
    MODEL_ID = "perplexity/sonar"
    PROVIDER = ModelProvider.OPENROUTER

    model: ChatModel = ChatModel(
        model_id=MODEL_ID,
        provider=PROVIDER,
        model=ChatOpenAI(
            model=MODEL_ID,
            temperature=0,
            timeout=120,
            max_retries=3,
            api_key=SecretStr(ABIModule.get_instance().configuration.openrouter_api_key),
            base_url=OPENROUTER_BASE_URL,
        ),
        context_window=127072,
        name="Perplexity: Sonar",
        owner="perplexity",
        description="Sonar is lightweight, affordable, fast, and simple to use — now featuring citations and the ability to customize sources. It is designed for companies seeking to integrate lightweight question-and-answer features...",
        canonical_slug="perplexity/sonar",
        hugging_face_id="",
        created_at=datetime.fromtimestamp(1738013808),
        pricing={'prompt': '0.000001', 'completion': '0.000001', 'web_search': '0.005'},
        architecture={'modality': 'text+image->text', 'input_modalities': ['text', 'image'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 127072, 'max_completion_tokens': 114364, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'max_tokens', 'presence_penalty', 'temperature', 'top_k', 'top_p', 'web_search_options'],
        default_parameters={},
    )


model: ChatModel = SonarModel.model
