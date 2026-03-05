# Model

## What it is
- Lightweight data holders for LangChain chat models and related metadata.
- Provides a base `Model` class and a `ChatModel` specialization with `context_window` and a `model_type`.

## Public API

### Enums
- `ModelType`
  - `CHAT`: Identifies chat-capable models.

### Classes
- `Model`
  - Purpose: Store a `langchain_core` `BaseChatModel` instance plus identifying and descriptive metadata.
  - Constructor:
    - `Model(model_id: str, provider: str, model: BaseChatModel, ..., default_parameters: Optional[dict] = None)`
  - Key attributes (all set directly on the instance):
    - Required: `model_id`, `provider`, `model`
    - Optional metadata: `name`, `owner`, `description`, `image`, `created_at`, `canonical_slug`, `hugging_face_id`
    - Optional structured info: `pricing`, `architecture`, `top_provider`, `per_request_limits`, `supported_parameters`, `default_parameters`

- `ChatModel(Model)`
  - Purpose: A `Model` with chat-specific fields.
  - Class attributes:
    - `model_type: ModelType = ModelType.CHAT`
  - Additional instance attributes:
    - `context_window: Optional[int]` — maximum context length in tokens
  - Constructor:
    - `ChatModel(model_id: str, provider: str, model: BaseChatModel, context_window: Optional[int] = None, ..., default_parameters: Optional[dict] = None)`

## Configuration/Dependencies
- Depends on:
  - `langchain_core.language_models.chat_models.BaseChatModel` (the wrapped chat model type)
  - `pydantic.Field` and `typing.Annotated` (used for type annotations/metadata only)
  - Standard library: `datetime`, `enum`, `typing.Optional`

## Usage

```python
from datetime import datetime
from naas_abi_core.models.Model import ChatModel

# `model` must be an actual LangChain BaseChatModel instance in real usage.
# Here we use a placeholder to show construction only.
model = object()  # replace with a real BaseChatModel

chat_model = ChatModel(
    model_id="gpt-4.1",
    provider="openai",
    model=model,  # should be a BaseChatModel
    context_window=128000,
    name="GPT-4.1",
    created_at=datetime.utcnow(),
)

print(chat_model.model_id)
print(chat_model.model_type)
print(chat_model.context_window)
```

## Caveats
- These classes are not Pydantic `BaseModel`s; the `Field(...)` metadata is not automatically enforced/validated at runtime.
- `model` is annotated as `BaseChatModel`, but there is no runtime type checking in `__init__`.
