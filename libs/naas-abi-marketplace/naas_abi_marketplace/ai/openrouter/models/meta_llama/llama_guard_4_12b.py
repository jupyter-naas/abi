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


class LlamaGuard412bModel(ModelDefinition):
    CANONICAL_ID = "llama-guard-4-12b"
    MODEL_ID = "meta-llama/llama-guard-4-12b"
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
        context_window=163840,
        name="Meta: Llama Guard 4 12B",
        owner="meta-llama",
        description="Llama Guard 4 is a Llama 4 Scout-derived multimodal pretrained model, fine-tuned for content safety classification. Similar to previous versions, it can be used to classify content in both LLM...",
        canonical_slug="meta-llama/llama-guard-4-12b",
        hugging_face_id="meta-llama/Llama-Guard-4-12B",
        created_at=datetime.fromtimestamp(1745975193),
        pricing={'prompt': '0.00000018', 'completion': '0.00000018'},
        architecture={'modality': 'text+image->text', 'input_modalities': ['image', 'text'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 163840, 'max_completion_tokens': 16384, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'logit_bias', 'max_tokens', 'min_p', 'presence_penalty', 'repetition_penalty', 'seed', 'stop', 'temperature', 'top_k', 'top_p'],
        default_parameters={},
    )


model: ChatModel = LlamaGuard412bModel.model
