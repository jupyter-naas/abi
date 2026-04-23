# Model

## What it is
- Lightweight data containers for describing AI models (primarily chat models) along with provider metadata.
- Uses `typing.Annotated` + `pydantic.Field` for field descriptions, but these classes are **not** Pydantic models.

## Public API

### `ModelType (Enum)`
- `CHAT`: identifies chat models.

### `class Model`
Container for a model instance and associated metadata.

**Constructor**
- `Model(model_id: str, provider: str, model: BaseChatModel, ..., default_parameters: Optional[dict] = None)`

**Attributes (set by `__init__`)**
- `model_id: str` — unique identifier.
- `provider: str` — provider name (e.g., `"openai"`, `"anthropic"`).
- `model: BaseChatModel` — LangChain chat model instance.
- Optional metadata:
  - `name`, `owner`, `description`, `image`
  - `created_at: datetime`
  - `canonical_slug`, `hugging_face_id`
  - `pricing: dict`, `architecture: dict`, `top_provider: dict`
  - `per_request_limits: dict`
  - `supported_parameters: list`
  - `default_parameters: dict`

### `class ChatModel(Model)`
Specialization for chat models.

**Constructor**
- `ChatModel(model_id: str, provider: str, model: BaseChatModel, context_window: Optional[int] = None, ..., default_parameters: Optional[dict] = None)`

**Additional attributes**
- `context_window: Optional[int]` — maximum context length in tokens.
- `model_type: ModelType` — set to `ModelType.CHAT`.

## Configuration/Dependencies
- `langchain_core.language_models.chat_models.BaseChatModel` (required type for `model`).
- `pydantic.Field` is used only to attach descriptions in type annotations; no runtime validation is performed by these classes.

## Usage
```python
from langchain_core.language_models.chat_models import BaseChatModel
from naas_abi_core.models.Model import ChatModel

# You must supply an actual LangChain BaseChatModel implementation.
chat_backend: BaseChatModel = ...

m = ChatModel(
    model_id="gpt-4.1",
    provider="openai",
    model=chat_backend,
    context_window=128000,
    name="GPT-4.1",
)

print(m.model_type)        # ModelType.CHAT
print(m.context_window)    # 128000
print(m.provider)          # "openai"
```

## Caveats
- These are plain Python classes (not `pydantic.BaseModel` / dataclasses):
  - No automatic validation, parsing, or serialization is provided.
  - `Field(...)` metadata is not enforced at runtime.
