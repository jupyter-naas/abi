# Gpt54BedrockModel

## What it is
- A Bedrock-backed `ModelDefinition` that configures an OpenAI GPT-5.4 chat model (`openai.gpt-5.4`) using `langchain_aws.ChatBedrockConverse`.
- Exposes a ready-to-use `ChatModel` instance for use elsewhere in the application.

## Public API
- **`class Gpt54BedrockModel(ModelDefinition)`**
  - **Purpose:** Defines metadata and an instantiated `ChatModel` for GPT-5.4 on Amazon Bedrock.
  - **Class attributes:**
    - `CANONICAL_ID`: `CanonicalModelId.GPT_5_4`
    - `MODEL_ID`: `"openai.gpt-5.4"`
    - `PROVIDER`: `ModelProvider.BEDROCK`
    - `model: ChatModel`: Preconfigured `ChatModel` wrapping `ChatBedrockConverse`
- **`model: ChatModel`** (module-level)
  - **Purpose:** Convenience alias to `Gpt54BedrockModel.model`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_aws.ChatBedrockConverse`
  - `naas_abi_core.models.Model` (`CanonicalModelId`, `ChatModel`, `ModelDefinition`, `ModelProvider`)
  - `naas_abi_marketplace.ai.bedrock.ABIModule`
- **Configuration source**
  - Uses `ABIModule.get_instance().configuration` to supply AWS settings:
    - `region_name`
    - `aws_access_key_id`
    - `aws_secret_access_key`
    - `aws_session_token`
- **Model settings (as configured)**
  - `temperature=0`
  - `max_tokens=None`
  - `context_window=1050000` (metadata on `ChatModel`)

## Usage
```python
from naas_abi_marketplace.ai.bedrock.models.openai.gpt_5_4 import model

# `model` is a ChatModel wrapper; access the underlying LangChain model via `.model`
llm = model.model

# Example: invoke depending on your LangChain version/setup
# response = llm.invoke("Hello from GPT-5.4 on Bedrock")
# print(response)
```

## Caveats
- Requires valid AWS credentials and region configuration via `ABIModule` configuration; otherwise model construction/authentication may fail at runtime.
- The module instantiates the Bedrock client/model at import time (via class attribute initialization).
