# O3DeepResearchModel

## What it is
- Defines and exports a preconfigured LangChain `ChatOpenAI` chat model for OpenAI’s `o3-deep-research`, wrapped in `naas_abi_core`’s `ChatModel`.

## Public API
- `class O3DeepResearchModel(ModelDefinition)`
  - Model definition container with constants and a prebuilt `ChatModel`.
  - Attributes:
    - `CANONICAL_ID`: `CanonicalModelId.O3_DEEP_RESEARCH`
    - `MODEL_ID`: `"o3-deep-research"`
    - `PROVIDER`: `ModelProvider.OPENAI`
    - `model: ChatModel`: wrapper around `ChatOpenAI(model="o3-deep-research", temperature=0, api_key=...)`
- `model: ChatModel`
  - Module-level export alias to `O3DeepResearchModel.model`.

## Configuration/Dependencies
- Dependencies:
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model`: `ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`
  - `naas_abi_marketplace.ai.chatgpt.ABIModule`
  - `pydantic.SecretStr`
- Required configuration:
  - `ABIModule.get_instance().configuration.openai_api_key` must be set; used to build the `ChatOpenAI` API key.

## Usage
```python
from naas_abi_marketplace.ai.chatgpt.models.o3_deep_research import model

llm = model.model  # underlying ChatOpenAI instance
# Use llm with LangChain as needed
```

## Caveats
- Importing this module requires a configured `ABIModule` with a valid `openai_api_key`.
- The module only provides a configured model instance; it does not implement prompt helpers or invocation utilities.
