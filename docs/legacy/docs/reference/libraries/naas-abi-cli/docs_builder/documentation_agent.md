# DocumentationAgent

## What it is
- A small helper that uses a LangChain OpenAI chat model to generate markdown documentation for a given Python source file.
- Reads source code and (optionally) existing docs, prompts the model, normalizes the model output, and can write the result to disk.

## Public API
- `class DocumentationAgent(model: str = "gpt-5.2")`
  - Initializes an agent backed by `langchain_openai.ChatOpenAI` with `temperature=0`.
- `DocumentationAgent.model_name -> str` (property)
  - Returns the configured model name.
- `DocumentationAgent.read_code_file(source_file: Path) -> str`
  - Reads Python source code from `source_file` as UTF-8 text.
- `DocumentationAgent.read_existing_documentation(target_file: Path) -> str | None`
  - Reads existing documentation from `target_file` if it exists; otherwise returns `None`.
- `DocumentationAgent.write_documentation_file(target_file: Path, markdown: str) -> None`
  - Creates parent directories as needed and writes `markdown` to `target_file` as UTF-8.
- `DocumentationAgent.generate_markdown(source_file: Path, target_file: Path) -> str`
  - Builds a prompt using the source code and any existing docs at `target_file`, invokes the chat model, and returns normalized markdown (always ends with `\n`).
- `DocumentationAgent.generate_and_write(source_file: Path, target_file: Path) -> str`
  - Runs `generate_markdown(...)`, writes the result to `target_file`, and returns the markdown.

## Configuration/Dependencies
- Dependency: `langchain_openai.ChatOpenAI`
  - The agent constructs `ChatOpenAI(model=model, temperature=0)`.
- File I/O uses `pathlib.Path` and assumes UTF-8 encoding.

## Usage
```python
from pathlib import Path
from naas_abi_cli.docs_builder.documentation_agent import DocumentationAgent

agent = DocumentationAgent(model="gpt-5.2")

source = Path("path/to/module.py")
target = Path("docs/module.md")

markdown = agent.generate_and_write(source, target)
print(markdown)
```

## Caveats
- Requires access/configuration for `ChatOpenAI` (e.g., environment/provider setup); failures will surface when invoking the model.
- `_normalize_markdown` strips a single outer fenced code block (```markdown/```md/```), if the model returns one.
