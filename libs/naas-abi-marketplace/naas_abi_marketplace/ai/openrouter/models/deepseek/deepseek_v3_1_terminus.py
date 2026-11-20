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


class DeepseekV31TerminusModel(ModelDefinition):
    CANONICAL_ID = "deepseek-v3.1-terminus"
    MODEL_ID = "deepseek/deepseek-v3.1-terminus"
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
        name="DeepSeek: DeepSeek V3.1 Terminus",
        owner="deepseek",
        description="DeepSeek-V3.1 Terminus is an update to [DeepSeek V3.1](/deepseek/deepseek-chat-v3.1) that maintains the model's original capabilities while addressing issues reported by users, including language consistency and agent capabilities, further optimizing the model's...",
        canonical_slug="deepseek/deepseek-v3.1-terminus",
        hugging_face_id="deepseek-ai/DeepSeek-V3.1-Terminus",
        created_at=datetime.fromtimestamp(1758548275),
        pricing={'prompt': '0.00000027', 'completion': '0.000001'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'DeepSeek', 'instruct_type': 'deepseek-v3.1'},
        top_provider={'context_length': 163840, 'max_completion_tokens': 147456, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'include_reasoning', 'max_tokens', 'reasoning', 'response_format', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_p'],
        default_parameters={'temperature': None, 'top_p': None, 'frequency_penalty': None},
    )


model: ChatModel = DeepseekV31TerminusModel.model
