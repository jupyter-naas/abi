# airgap_qwen

## What it is
- A module that defines a preconfigured `ChatModel` instance for the **Qwen3** chat model running in **airgap mode** via a local Docker Model Runner endpoint.

## Public API
- **Module constants**
  - `MODEL_ID`: `"ai/qwen3"`
  - `PROVIDER`: `"qwen"`
  - `NAME`: `"qwen3-airgap"`
  - `DESCRIPTION`: Human-readable description of the model setup
  - `IMAGE`: URL to a representative image
  - `CONTEXT_WINDOW`: `8192`
- **Module instance**
  - `model: ChatModel`: A `naas_abi_core.models.Model.ChatModel` wrapping a `langchain_openai.ChatOpenAI` client configured to talk to a local engine.

## Configuration/Dependencies
- **Python dependencies**
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model.ChatModel`
- **Runtime configuration (hardcoded in module)**
  - `base_url="http://localhost:12434/engines/v1"` (expects a local service listening there)
  - `model="ai/qwen3"`
  - `temperature=0.7`

## Usage
```python
from naas_abi.models.airgap_qwen import model

# Use `model` with the APIs expected by `ChatModel` in your environment.
# Example access to metadata:
print(model.model_id, model.provider, model.name)
```

## Caveats
- Requires a local engine reachable at `http://localhost:12434/engines/v1`; otherwise requests made through the underlying client will fail.
- This module only defines configuration and instantiates objects; it does not expose helper functions for invoking the model.
