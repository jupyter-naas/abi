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


class Llama323bInstructModel(ModelDefinition):
    CANONICAL_ID = "llama-3.2-3b-instruct"
    MODEL_ID = "meta-llama/llama-3.2-3b-instruct"
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
        context_window=131072,
        name="Meta: Llama 3.2 3B Instruct",
        owner="meta-llama",
        description="Llama 3.2 3B is a 3-billion-parameter multilingual large language model, optimized for advanced natural language processing tasks like dialogue generation, reasoning, and summarization. Designed with the latest transformer architecture, it...",
        canonical_slug="meta-llama/llama-3.2-3b-instruct",
        hugging_face_id="meta-llama/Llama-3.2-3B-Instruct",
        created_at=datetime.fromtimestamp(1727222400),
        pricing={'prompt': '0.0000000509', 'completion': '0.000000335'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Llama3', 'instruct_type': 'llama3'},
        top_provider={'context_length': 80000, 'max_completion_tokens': 72000, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'logit_bias', 'logprobs', 'max_tokens', 'min_p', 'presence_penalty', 'repetition_penalty', 'seed', 'stop', 'structured_outputs', 'temperature', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={},
    )


model: ChatModel = Llama323bInstructModel.model
