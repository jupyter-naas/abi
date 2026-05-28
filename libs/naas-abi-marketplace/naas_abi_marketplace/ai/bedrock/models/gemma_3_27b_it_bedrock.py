from langchain_aws import ChatBedrockConverse
from naas_abi_marketplace.ai.bedrock import ABIModule
from naas_abi_core.models.Model import ChatModel

MODEL_ID = "google.gemma-3-27b-it"
PROVIDER = "bedrock"

_config = ABIModule.get_instance().configuration

model: ChatModel = ChatModel(
    model_id=MODEL_ID,
    provider=PROVIDER,
    model=ChatBedrockConverse(
        model=MODEL_ID,
        region_name=_config.region_name,
        aws_access_key_id=_config.aws_access_key_id,
        aws_secret_access_key=_config.aws_secret_access_key,
        aws_session_token=_config.aws_session_token,
        temperature=0,
        max_tokens=None,
    ),
)
