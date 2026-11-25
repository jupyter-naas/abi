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


class MimoV25ProModel(ModelDefinition):
    CANONICAL_ID = "mimo-v2.5-pro"
    MODEL_ID = "xiaomi/mimo-v2.5-pro"
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
        context_window=262144,
        name="Xiaomi: MiMo-V2.5-Pro",
        owner="xiaomi",
        description="MiMo-V2.5-Pro is Xiaomi’s flagship model, delivering strong performance in general agentic capabilities, complex software engineering, and long-horizon tasks, with top rankings on benchmarks such as ClawEval, GDPVal, and SWE-bench Pro....",
        canonical_slug="xiaomi/mimo-v2.5-pro-20260422",
        hugging_face_id="XiaomiMiMo/MiMo-V2.5-Pro",
        created_at=datetime.fromtimestamp(1776874273),
        pricing={'prompt': '0.00000048', 'completion': '0.0000018', 'input_cache_read': '0.000000096'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 262144, 'max_completion_tokens': 235929, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['include_reasoning', 'logprobs', 'max_tokens', 'reasoning', 'response_format', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_logprobs', 'top_p'],
        default_parameters={'temperature': 1, 'top_p': 0.95, 'top_k': None, 'frequency_penalty': None, 'presence_penalty': None, 'repetition_penalty': None},
    )


model: ChatModel = MimoV25ProModel.model
