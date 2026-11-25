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


class CommandR082024Model(ModelDefinition):
    CANONICAL_ID = "command-r-08-2024"
    MODEL_ID = "cohere/command-r-08-2024"
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
        context_window=128000,
        name="Cohere: Command R (08-2024)",
        owner="cohere",
        description="command-r-08-2024 is an update of the [Command R](/models/cohere/command-r) with improved performance for multilingual retrieval-augmented generation (RAG) and tool use. More broadly, it is better at math, code and reasoning and...",
        canonical_slug="cohere/command-r-08-2024",
        hugging_face_id="CohereLabs/c4ai-command-r-08-2024",
        created_at=datetime.fromtimestamp(1724976000),
        pricing={'prompt': '0.00000015', 'completion': '0.0000006'},
        architecture={'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'Cohere', 'instruct_type': None},
        top_provider={'context_length': 128000, 'max_completion_tokens': 4000, 'is_moderated': True},
        per_request_limits=None,
        supported_parameters=['frequency_penalty', 'max_tokens', 'presence_penalty', 'response_format', 'seed', 'stop', 'structured_outputs', 'temperature', 'tool_choice', 'tools', 'top_k', 'top_p'],
        default_parameters={},
    )


model: ChatModel = CommandR082024Model.model
