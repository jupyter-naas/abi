from datetime import datetime

from langchain_openai import ChatOpenAI
from naas_abi_core.models.Model import (
    CanonicalModelId,
    ChatModel,
    ModelDefinition,
    ModelProvider,
)
from naas_abi_marketplace.ai.openrouter import ABIModule
from pydantic import SecretStr

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class Codestral2508Model(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.CODESTRAL_2508
    MODEL_ID = "mistralai/codestral-2508"
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
        context_window=256000,
        name="Mistral: Codestral 2508",
        owner="mistralai",
        description="Mistral's cutting-edge language model for coding released end of July 2025. Codestral specializes in low-latency, high-frequency tasks such as fill-in-the-middle (FIM), code correction and test generation.\n\n[Blog Post](https://mistral.ai/news/codestral-25-08)",
        canonical_slug="mistralai/codestral-2508",
        hugging_face_id="",
        created_at=datetime.fromtimestamp(1754079630),
        pricing={'prompt': '0.0000003', 'completion': '0.0000009', 'input_cache_read': '0.00000003'},
        architecture={'modality': 'text+file->text', 'input_modalities': ['text', 'file'], 'output_modalities': ['text'], 'tokenizer': 'Mistral', 'instruct_type': None},
        top_provider={'context_length': 256000, 'max_completion_tokens': None, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'max_tokens', 'presence_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_p'],
        default_parameters={'temperature': 0.3},
    )


model: ChatModel = Codestral2508Model.model
