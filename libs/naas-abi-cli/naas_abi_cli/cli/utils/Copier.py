import os
import shutil
import subprocess
import sys

import jinja2
from jinja2 import Environment, meta
from rich.prompt import Prompt


class ValueProvider(dict):
    def collect_values(self, template_string: str) -> None:
        env = Environment()  # nosec B701 - autoescape not needed; Environment is used only for AST parsing (meta.find_undeclared_variables), never for rendering HTML output
        ast = env.parse(template_string)
        needed = meta.find_undeclared_variables(ast)

        for name in sorted(needed):
            if name in self:
                continue
            self[name] = Prompt.ask(f"Enter value for '{name}'")


class Copier:
    templates_path: str
    destination_path: str
    values: dict

    def __init__(self, templates_path: str, destination_path: str):
        # Normalize paths to avoid double-joining relative segments during recursion.
        self.templates_path = os.path.abspath(templates_path)
        self.destination_path = os.path.abspath(destination_path)
        # Files this Copier wrote, so the post-render format pass touches only
        # generated code and never the rest of the user's project.
        self._generated_files: list[str] = []

    def _template_file_to_file(self, template_path: str, destination_path: str) -> None:
        destination_path = self._template_string(destination_path)
        with open(destination_path, "w", encoding="utf-8") as file:
            file.write(self._template_file(template_path))
        self._generated_files.append(destination_path)

    def _template_file(self, template_path: str) -> str:
        with open(template_path, "r", encoding="utf-8") as file:
            return self._template_string(file.read())

    def _template_string(self, template_string: str) -> str:
        vp = ValueProvider(self.values)
        vp.collect_values(template_string)
        self.values = {**self.values, **vp}
        # keep_trailing_newline: Jinja strips a single trailing newline by
        # default, which would emit generated files with no final newline --
        # `ruff format --check` rejects those. Harmless for the rendered
        # path strings this also handles, since paths carry no trailing newline.
        return jinja2.Template(template_string, keep_trailing_newline=True).render(
            self.values
        )

    def _format_generated_python(self) -> None:
        """Best-effort `ruff format` over the Python files we just wrote.

        Rendering shifts line lengths -- a name longer or shorter than the
        `{{placeholder}}` moves wrapping -- so a template that is itself
        formatter-clean still renders unformatted code for some names. The only
        reliable fix is to format *after* rendering.

        Ruff is not a runtime dependency of this CLI, so a missing binary is not
        an error: the generated code is valid either way, it just may not match
        `ruff format`. Never let this step break generation.
        """
        targets = [f for f in self._generated_files if f.endswith(".py")]
        if not targets:
            return

        ruff = shutil.which("ruff")
        command = [ruff] if ruff else [sys.executable, "-m", "ruff"]

        try:
            subprocess.run(  # nosec B603 - fixed argv, paths are ones we just wrote
                [*command, "format", "--quiet", *targets],
                capture_output=True,
                check=False,
                timeout=120,
            )
        except (OSError, subprocess.SubprocessError):
            # No ruff available, or it failed/timed out. Generation still succeeded.
            pass

    def copy(self, values: dict, templates_path: str | None = None):
        self.values = values

        # Only the outermost call formats, once the whole tree has been written.
        is_root_call = templates_path is None
        if is_root_call:
            self._generated_files = []

        if templates_path is None:
            templates_path = self.templates_path
        elif not os.path.isabs(templates_path):
            templates_path = os.path.join(self.templates_path, templates_path)

        relative_templates_path = os.path.relpath(
            templates_path, start=self.templates_path
        )
        target_path = (
            self.destination_path
            if relative_templates_path == "."
            else os.path.join(self.destination_path, relative_templates_path)
        )

        for file in os.listdir(templates_path):
            if os.path.isfile(os.path.join(templates_path, file)):
                if False:
                    shutil.copy(
                        os.path.join(templates_path, file),
                        self._template_string(os.path.join(target_path, file)),
                    )
                else:
                    self._template_file_to_file(
                        os.path.join(templates_path, file),
                        os.path.join(target_path, file),
                    )
            elif os.path.isdir(os.path.join(templates_path, file)):
                os.makedirs(
                    self._template_string(os.path.join(target_path, file)),
                    exist_ok=True,
                )
                self.copy(self.values, os.path.join(templates_path, file))
            else:
                print(f"Skipping {file}")

        if is_root_call:
            self._format_generated_python()
