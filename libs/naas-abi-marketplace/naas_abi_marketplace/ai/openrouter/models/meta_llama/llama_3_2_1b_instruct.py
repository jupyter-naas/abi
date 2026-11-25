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


class Llama321bInstructModel(ModelDefinition):
    CANONICAL_ID = "llama-3.2-1b-instruct"
    MODEL_ID = "meta-llama/llama-3.2-1b-instruct"
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
        context_window=60000,
        name="Meta: Llama 3.2 1B Instruct",
        owner="meta-llama",
        description="Llama 3.2 1B is a 1-billion-parameter language model focused on efficiently performing natural language tasks, such as summarization, dialogue, and multilingual text analysis. Its smaller size allows it to operate...",
        canonical_slug="meta-llama/llama-3.2-1b-instruct",
        hugging_face_id="meta-llama/Llama-3.2-1B-Instruct",
        created_at=datetime.fromtimestamp(1727222400),
        pricing={'prompt': '0.000000027', 'completion': '0.000000201'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Llama3', 'instruct_type': 'llama3'},
        top_provider={'context_length': 60000, 'max_completion_tokens': 54000, 'is_moderated': False},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'logit_bias', 'max_tokens', 'min_p', 'presence_penalty', 'repetition_penalty', 'seed', 'stop', 'temperature', 'top_k', 'top_p'],
        default_parameters={},
    )


model: ChatModel = Llama321bInstructModel.model
