from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from langchain_openai import ChatOpenAI


class DocumentationAgent:
    def __init__(self, model: str = "gpt-5.2") -> None:
        self._model_name = model
        self._model = ChatOpenAI(model=model, temperature=0)

    @property
    def model_name(self) -> str:
        return self._model_name

    def read_code_file(self, source_file: Path) -> str:
        return source_file.read_text(encoding="utf-8")

    def read_existing_documentation(self, target_file: Path) -> str | None:
        if not target_file.exists():
            return None
        return target_file.read_text(encoding="utf-8")

    def write_documentation_file(self, target_file: Path, markdown: str) -> None:
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(markdown, encoding="utf-8")

    def _build_prompt(
        self,
        source_file: Path,
        source_code: str,
        existing_documentation: str | None,
    ) -> str:
        existing_doc_section = (
            existing_documentation if existing_documentation is not None else "<none>"
        )
        return f"""
You are a technical documentation agent.

Task:
- Generate markdown documentation for the Python file at `{source_file}`.
- Output markdown only (no commentary before or after).
- Keep it concise and accurate.
- Do not invent behavior not present in code.

Required structure:
1. Title (`# ...`) based on the main class/function/module name.
2. Short "What it is" section.
3. "Public API" section listing public classes/functions/methods and purpose.
4. "Configuration/Dependencies" section when relevant.
5. "Usage" section with a minimal runnable example when possible.
6. "Caveats" section only if there are important constraints.

Style constraints:
- Use clear operator-focused language.
- Prefer bullet lists over long paragraphs.
- Keep code snippets short and valid Python.

Existing documentation (if any):
```markdown
{existing_doc_section}
```

Source code:
```python
{source_code}
```
""".strip()

    def _normalize_markdown(self, content: Any) -> str:
        text = content if isinstance(content, str) else str(content)
        stripped = text.strip()
        fenced_match = re.match(r"^```(?:markdown|md)?\n([\s\S]*?)\n```$", stripped)
        if fenced_match:
            stripped = fenced_match.group(1).strip()
        return stripped + "\n"

    def generate_markdown(self, source_file: Path, target_file: Path) -> str:
        source_code = self.read_code_file(source_file)
        existing_doc = self.read_existing_documentation(target_file)
        prompt = self._build_prompt(source_file, source_code, existing_doc)
        response = self._model.invoke(prompt)
        response_content = getattr(response, "content", response)
        return self._normalize_markdown(response_content)

    def generate_and_write(self, source_file: Path, target_file: Path) -> str:
        markdown = self.generate_markdown(source_file, target_file)
        self.write_documentation_file(target_file, markdown)
        return markdown
