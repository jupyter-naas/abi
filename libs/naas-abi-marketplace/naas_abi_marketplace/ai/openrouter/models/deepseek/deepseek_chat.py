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


class DeepseekChatModel(ModelDefinition):
    CANONICAL_ID = "deepseek-chat"
    MODEL_ID = "deepseek/deepseek-chat"
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
        name="DeepSeek: DeepSeek V3",
        owner="deepseek",
        description="DeepSeek-V3 is the latest model from the DeepSeek team, building upon the instruction following and coding abilities of the previous versions. Pre-trained on nearly 15 trillion tokens, the reported evaluations...",
        canonical_slug="deepseek/deepseek-chat-v3",
        hugging_face_id="deepseek-ai/DeepSeek-V3",
        created_at=datetime.fromtimestamp(1735241320),
        pricing={'prompt': '0.0000002574', 'completion': '0.0000010287'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'DeepSeek', 'instruct_type': None},
        top_provider={'context_length': 128000, 'max_completion_tokens': 16000, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'logit_bias', 'max_tokens', 'min_p', 'presence_penalty', 'repetition_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_p'],
        default_parameters={},
    )


model: ChatModel = DeepseekChatModel.model
