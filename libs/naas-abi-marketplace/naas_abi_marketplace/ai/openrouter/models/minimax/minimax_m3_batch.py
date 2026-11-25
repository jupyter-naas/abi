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


class MinimaxM3BatchModel(ModelDefinition):
    CANONICAL_ID = "minimax-m3:batch"
    MODEL_ID = "minimax/minimax-m3:batch"
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
        context_window=524288,
        name="MiniMax: MiniMax M3 (batch)",
        owner="minimax",
        description="MiniMax-M3 is a multimodal foundation model from MiniMax. It supports text, image, and video inputs with text output, a 1M-token context window, and is suited for long-horizon agentic work, coding,...",
        canonical_slug="minimax/minimax-m3-20260531",
        hugging_face_id="MiniMaxAI/Minimax-M3",
        created_at=datetime.fromtimestamp(1780245374),
        pricing={'prompt': '0.000000224', 'completion': '0.00000088', 'input_cache_read': '0.0000000448'},
        architecture={'modality': 'text+image+video->text', 'input_modalities': ['text', 'image', 'video'], 'output_modalities': ['text'], 'tokenizer': 'Other', 'instruct_type': None},
        top_provider={'context_length': 524288, 'max_completion_tokens': 512000, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'logit_bias', 'max_tokens', 'min_p', 'presence_penalty', 'reasoning', 'repetition_penalty', 'response_format', 'seed', 'stop', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_p'],
        default_parameters={'temperature': 1, 'top_p': 0.95, 'top_k': None, 'frequency_penalty': None, 'presence_penalty': None, 'repetition_penalty': None},
    )


model: ChatModel = MinimaxM3BatchModel.model
