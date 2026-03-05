# airgap_qwen

## What it is
- A module that defines a preconfigured `ChatModel` instance for the Qwen3 model running in “airgap” mode via a local Docker Model Runner endpoint.

## Public API
- **Module constants**
  - `MODEL_ID`: `"ai/qwen3"`
  - `PROVIDER`: `"qwen"`
  - `NAME`: `"qwen3-airgap"`
  - `DESCRIPTION`: Human-readable description of the model configuration.
  - `IMAGE`: URL for a representative image.
  - `CONTEXT_WINDOW`: `8192` (declared, not wired into the `ChatModel` in this file)
- **Module variable**
  - `model: ChatModel`: A `ChatModel` wrapping a `langchain_openai.ChatOpenAI` client configured to talk to a local endpoint.

## Configuration/Dependencies
- **Python dependencies**
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model.ChatModel`
- **Runtime dependency**
  - A service reachable at: `http://localhost:12434/engines/v1`
- **Model configuration**
  - `ChatOpenAI(model="ai/qwen3", temperature=0.7, base_url="http://localhost:12434/engines/v1")`

## Usage
```python
from naas_abi.models.airgap_qwen import model

# Access metadata
print(model.model_id)     # "ai/qwen3"
print(model.provider)     # "qwen"
print(model.name)         # "qwen3-airgap"

# Access the underlying LangChain chat model/client
llm = model.model
print(llm)
```

## Caveats
- The module only defines configuration; successful usage requires a compatible local server running at `http://localhost:12434/engines/v1`.
- `CONTEXT_WINDOW` is declared but not applied to the `ChatOpenAI`/`ChatModel` configuration in this file.
