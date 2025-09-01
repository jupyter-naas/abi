from lib.abi.models.Model import ChatModel
from langchain_aws import ChatBedrockConverse  # type: ignore


model = ChatModel(
    model_id="1ef84540-0000-4000-8000-000000000000",
    name="AWS Bedrock Anthropic Claude 3.5 Sonnet",
    description="AWS Bedrock Anthropic Claude 3.5 Sonnet",
    image="",
    owner="aws-bedrock",
    model=ChatBedrockConverse(
        model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
    ),
    context_window=200000,
)
