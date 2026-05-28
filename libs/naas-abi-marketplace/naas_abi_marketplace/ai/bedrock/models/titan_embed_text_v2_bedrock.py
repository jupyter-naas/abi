from langchain_aws import BedrockEmbeddings
from naas_abi_marketplace.ai.bedrock import ABIModule

MODEL_ID = "amazon.titan-embed-text-v2:0"
PROVIDER = "bedrock"

_config = ABIModule.get_instance().configuration

embedding_model = BedrockEmbeddings(
    model_id=MODEL_ID,
    region_name=_config.region_name,
    aws_access_key_id=_config.aws_access_key_id,
    aws_secret_access_key=_config.aws_secret_access_key,
    aws_session_token=_config.aws_session_token,
)
