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


class Qwen35Plus0215Model(ModelDefinition):
    CANONICAL_ID = "qwen3.5-plus-02-15"
    MODEL_ID = "qwen/qwen3.5-plus-02-15"
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
        context_window=1000000,
        name="Qwen: Qwen3.5 Plus 2026-02-15",
        owner="qwen",
        description="The Qwen3.5 native vision-language series Plus models are built on a hybrid architecture that integrates linear attention mechanisms with sparse mixture-of-experts models, achieving higher inference efficiency. In a variety of...",
        canonical_slug="qwen/qwen3.5-plus-20260216",
        hugging_face_id="",
        created_at=datetime.fromtimestamp(1771229416),
        pricing={'prompt': '0.00000026', 'completion': '0.00000156', 'overrides': [{'min_prompt_tokens': 256000, 'prompt': '0.000000325', 'completion': '0.00000195'}]},
        architecture={'modality': 'text+image+video->text', 'input_modalities': ['text', 'image', 'video'], 'output_modalities': ['text'], 'tokenizer': 'Qwen3', 'instruct_type': None},
        top_provider={'context_length': 1000000, 'max_completion_tokens': 65536, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logprobs', 'max_tokens', 'presence_penalty', 'reasoning', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={'temperature': None, 'top_p': None, 'frequency_penalty': None},
    )


model: ChatModel = Qwen35Plus0215Model.model
