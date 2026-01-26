import os
import shutil

import jinja2
from jinja2 import Environment, meta
from rich.prompt import Prompt


class ValueProvider(dict):
    def collect_values(self, template_string: str) -> None:
        env = Environment()  # add your filters/tests if you use them
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

    def _template_file_to_file(
        self, template_path: str, values: ValueProvider, destination_path: str
    ) -> None:
        destination_path = self._template_string(destination_path, values)
        with open(destination_path, "w", encoding="utf-8") as file:
            file.write(self._template_file(template_path, values))

    def _template_file(self, template_path: str, values: ValueProvider) -> str:
        with open(template_path, "r", encoding="utf-8") as file:
            return self._template_string(file.read(), values)

    def _template_string(self, template_string: str, values: ValueProvider) -> str:
        values.collect_values(template_string)
        return jinja2.Template(template_string).render(values)

    def copy(self, values: dict, templates_path: str | None = None):
        vp = ValueProvider(values)

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
                if False and "config" in file and file.endswith(".yaml"):
                    shutil.copy(
                        os.path.join(templates_path, file),
                        self._template_string(os.path.join(target_path, file), vp),
                    )
                else:
                    self._template_file_to_file(
                        os.path.join(templates_path, file),
                        vp,
                        os.path.join(target_path, file),
                    )
            elif os.path.isdir(os.path.join(templates_path, file)):
                os.makedirs(
                    self._template_string(os.path.join(target_path, file), vp),
                    exist_ok=True,
                )
                self.copy(values, os.path.join(templates_path, file))
            else:
                print(f"Skipping {file}")
                print(f"Skipping {file}")
