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


class Qwen25Coder32bInstructModel(ModelDefinition):
    CANONICAL_ID = "qwen-2.5-coder-32b-instruct"
    MODEL_ID = "qwen/qwen-2.5-coder-32b-instruct"
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
        context_window=32768,
        name="Qwen2.5 Coder 32B Instruct",
        owner="qwen",
        description="Qwen2.5-Coder is the latest series of Code-Specific Qwen large language models (formerly known as CodeQwen). Qwen2.5-Coder brings the following improvements upon CodeQwen1.5: - Significantly improvements in **code generation**, **code reasoning**...",
        canonical_slug="qwen/qwen-2.5-coder-32b-instruct",
        hugging_face_id="Qwen/Qwen2.5-Coder-32B-Instruct",
        created_at=datetime.fromtimestamp(1731368400),
        pricing={'prompt': '0.00000066', 'completion': '0.000001'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Qwen', 'instruct_type': 'chatml'},
        top_provider={'context_length': 32768, 'max_completion_tokens': 29491, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'logit_bias', 'max_tokens', 'min_p', 'presence_penalty', 'repetition_penalty', 'response_format', 'seed', 'stop', 'temperature', 'top_k', 'top_p'],
        default_parameters={},
    )


model: ChatModel = Qwen25Coder32bInstructModel.model
