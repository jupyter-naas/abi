# Gpt55BedrockModel

## What it is
- Defines a Bedrock-backed chat model configuration for **OpenAI GPT-5.5** using `langchain_aws.ChatBedrockConverse`.
- Exposes a ready-to-use `ChatModel` instance as `Gpt55BedrockModel.model` and as a module-level alias `model`.

## Public API
- `class Gpt55BedrockModel(ModelDefinition)`
  - Static model definition for the GPT-5.5 Bedrock model.
  - Public attributes:
    - `CANONICAL_ID`: `CanonicalModelId.GPT_5_5`
    - `MODEL_ID`: `"openai.gpt-5.5"`
    - `PROVIDER`: `ModelProvider.BEDROCK`
    - `model: ChatModel`: Preconfigured chat model wrapper.
- `model: ChatModel`
  - Module-level alias to `Gpt55BedrockModel.model`.

## Configuration/Dependencies
- Dependencies:
  - `langchain_aws.ChatBedrockConverse`
  - `naas_abi_core.models.Model` (`CanonicalModelId`, `ChatModel`, `ModelDefinition`, `ModelProvider`)
  - `naas_abi_marketplace.ai.bedrock.ABIModule`
- Configuration source:
  - `ABIModule.get_instance().configuration` provides:
    - `region_name`
    - `aws_access_key_id`
    - `aws_secret_access_key`
    - `aws_session_token`
- Model runtime parameters set here:
  - `temperature=0`
  - `max_tokens=None`
  - `context_window=1050000` (stored on `ChatModel`)

## Usage
```python
from naas_abi_marketplace.ai.bedrock.models.openai.gpt_5_5 import model

# `model.model` is the underlying ChatBedrockConverse instance.
llm = model.model

# Example invocation depends on your LangChain version; commonly:
result = llm.invoke("Say hello in one sentence.")
print(result)
```

## Caveats
- Requires valid AWS credentials and Bedrock access for `openai.gpt-5.5` in the configured region.
- `max_tokens=None` means token limit behavior is delegated to the underlying client/defaults.
