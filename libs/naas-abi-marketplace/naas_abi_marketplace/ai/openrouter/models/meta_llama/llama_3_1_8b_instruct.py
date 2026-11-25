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


class Llama318bInstructModel(ModelDefinition):
    CANONICAL_ID = "llama-3.1-8b-instruct"
    MODEL_ID = "meta-llama/llama-3.1-8b-instruct"
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
        name="Meta: Llama 3.1 8B Instruct",
        owner="meta-llama",
        description="Meta's latest class of model (Llama 3.1) launched with a variety of sizes & flavors. This 8B instruct-tuned version is fast and efficient. It has demonstrated strong performance compared to...",
        canonical_slug="meta-llama/llama-3.1-8b-instruct",
        hugging_face_id="meta-llama/Meta-Llama-3.1-8B-Instruct",
        created_at=datetime.fromtimestamp(1721692800),
        pricing={'prompt': '0.00000002', 'completion': '0.00000004'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Llama3', 'instruct_type': 'llama3'},
        top_provider={'context_length': 131072, 'max_completion_tokens': 16384, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'logit_bias', 'logprobs', 'max_tokens', 'min_p', 'presence_penalty', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={},
    )


model: ChatModel = Llama318bInstructModel.model
