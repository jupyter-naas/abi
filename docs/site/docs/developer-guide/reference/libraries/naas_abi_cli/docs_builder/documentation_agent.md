# DocumentationAgent

## What it is
- A small utility class that generates Markdown documentation for a Python source file using a LangChain `ChatOpenAI` model.
- Reads source code and any existing docs, builds a prompt, invokes the model, normalizes the returned Markdown, and optionally writes it to disk.

## Public API
- `class DocumentationAgent(model: str = "gpt-5.2")`
  - Creates an agent backed by `langchain_openai.ChatOpenAI` with `temperature=0`.
- `DocumentationAgent.model_name -> str` (property)
  - Returns the configured model name.
- `DocumentationAgent.read_code_file(source_file: Path) -> str`
  - Reads a UTF-8 source file into a string.
- `DocumentationAgent.read_existing_documentation(target_file: Path) -> str | None`
  - Reads a UTF-8 target file if it exists; otherwise returns `None`.
- `DocumentationAgent.write_documentation_file(target_file: Path, markdown: str) -> None`
  - Ensures the target directory exists and writes UTF-8 Markdown to `target_file`.
- `DocumentationAgent.generate_markdown(source_file: Path, target_file: Path) -> str`
  - Generates Markdown by:
    - reading `source_file`
    - reading existing docs from `target_file` (if present)
    - building an LLM prompt
    - invoking the LLM
    - normalizing the output to plain Markdown (and ensuring a trailing newline)
- `DocumentationAgent.generate_and_write(source_file: Path, target_file: Path) -> str`
  - Calls `generate_markdown(...)`, writes it to `target_file`, and returns the Markdown.

## Configuration/Dependencies
- Depends on:
  - `langchain_openai.ChatOpenAI`
  - Standard library: `pathlib.Path`, `re`, `typing.Any`
- LLM configuration:
  - Model name defaults to `"gpt-5.2"` (override via constructor)
  - `temperature=0` is hard-coded

## Usage
```python
from pathlib import Path
from naas_abi_cli.docs_builder.documentation_agent import DocumentationAgent

agent = DocumentationAgent(model="gpt-5.2")

source = Path("some_module.py")
target = Path("docs/some_module.md")

markdown = agent.generate_and_write(source, target)
print(markdown)
```

## Caveats
- Requires a working `langchain_openai` setup (credentials/environment handled outside this module).
- Output normalization strips a single top-level fenced code block (```markdown/```md/```) if the model returns one, and always appends a trailing newline.
