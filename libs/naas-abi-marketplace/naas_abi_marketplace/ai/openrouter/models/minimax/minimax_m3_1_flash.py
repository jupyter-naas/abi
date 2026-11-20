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


class MinimaxM31FlashModel(ModelDefinition):
    CANONICAL_ID = "minimax-m3.1-flash"
    MODEL_ID = "minimax/minimax-m3.1-flash"
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
        name="MiniMax: MiniMax M3.1 Flash",
        owner="minimax",
        description="MiniMax-M3.1-Flash is a multimodal model from MiniMax. Compared with M3, it delivers significant improvements across multiple benchmarks, particularly in complex agentic tasks, coding, and cybersecurity. It is built for complex,...",
        canonical_slug="minimax/minimax-m3.1-flash-20261019",
        hugging_face_id="MiniMaxAI/MiniMax-M3.1-Flash",
        created_at=datetime.fromtimestamp(1792379569),
        pricing={'prompt': '0.000000075', 'completion': '0.0000003', 'input_cache_read': '0.0000000075', 'overrides': [{'utc_start': 1500, 'utc_end': 100, 'prompt': '0.000000075', 'completion': '0.0000003', 'input_cache_read': '0.0000000075'}, {'utc_start': 100, 'utc_end': 1500, 'prompt': '0.00000015', 'completion': '0.0000006', 'input_cache_read': '0.000000015'}]},
        architecture={'modality': 'text+image+video->text', 'input_modalities': ['text', 'image', 'video'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 1048576, 'max_completion_tokens': 524288, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logit_bias', 'logprobs', 'max_tokens', 'min_p', 'presence_penalty', 'reasoning', 'reasoning_effort', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_logprobs', 'top_p'],
        default_parameters={},
    )


model: ChatModel = MinimaxM31FlashModel.model
