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


class KimiK31ProModel(ModelDefinition):
    CANONICAL_ID = "kimi-k3.1-pro"
    MODEL_ID = "moonshotai/kimi-k3.1-pro"
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
        context_window=1048576,
        name="MoonshotAI: Kimi K3.1 Pro",
        owner="moonshotai",
        description="Kimi K3.1 Pro is Moonshot AI's flagship open-weight multimodal reasoning model and a post-trained successor to Kimi K3, with a 1M-token context window. It is built for long-horizon coding, 3D...",
        canonical_slug="moonshotai/kimi-k3.1-pro-20261023",
        hugging_face_id="moonshotai/Kimi-K3.1-Pro",
        created_at=datetime.fromtimestamp(1792778188),
        pricing={'prompt': '0.000000253', 'completion': '0.0000088', 'input_cache_read': '0.00000018'},
        architecture={'modality': 'text+image+video->text', 'input_modalities': ['text', 'image', 'video'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 1048576, 'max_completion_tokens': 943718, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logit_bias', 'logprobs', 'max_tokens', 'min_p', 'presence_penalty', 'reasoning', 'reasoning_effort', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={'top_p': 0.95},
    )


model: ChatModel = KimiK31ProModel.model
