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


class SonarDeepResearchModel(ModelDefinition):
    CANONICAL_ID = "sonar-deep-research"
    MODEL_ID = "perplexity/sonar-deep-research"
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
        context_window=128000,
        name="Perplexity: Sonar Deep Research",
        owner="perplexity",
        description="Sonar Deep Research is a research-focused model designed for multi-step retrieval, synthesis, and reasoning across complex topics. It autonomously searches, reads, and evaluates sources, refining its approach as it gathers...",
        canonical_slug="perplexity/sonar-deep-research",
        hugging_face_id="",
        created_at=datetime.fromtimestamp(1741311246),
        pricing={'prompt': '0.000002', 'completion': '0.000008', 'web_search': '0.005', 'internal_reasoning': '0.000003'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': 'deepseek-r1'},
        top_provider={'context_length': 128000, 'max_completion_tokens': 115200, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'max_tokens', 'presence_penalty', 'reasoning', 'temperature', 'top_k', 'top_p', 'web_search_options'],
        default_parameters={},
    )


model: ChatModel = SonarDeepResearchModel.model
