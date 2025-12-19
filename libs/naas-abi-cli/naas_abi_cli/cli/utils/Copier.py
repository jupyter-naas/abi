import os
import shutil

import jinja2


class Copier:
    templates_path: str
    destination_path: str
    values: dict

    def __init__(self, templates_path: str, destination_path: str):
        self.templates_path = templates_path
        self.destination_path = destination_path

    def template_file_to_file(
        self, template_path: str, values: dict, destination_path: str
    ) -> None:
        destination_path = self.template_string(destination_path, values)
        with open(destination_path, "w", encoding="utf-8") as file:
            file.write(self.template_file(template_path, values))

    def template_file(self, template_path: str, values: dict) -> str:
        with open(template_path, "r", encoding="utf-8") as file:
            return self.template_string(file.read(), values)

    def template_string(self, template_string: str, values: dict) -> str:
        return jinja2.Template(template_string).render(values)

    def copy(self, values: dict, templates_path: str | None = None):
        if templates_path is None:
            templates_path = self.templates_path
        else:
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
                if "config" in file and file.endswith(".yaml"):
                    shutil.copy(
                        os.path.join(templates_path, file),
                        self.template_string(os.path.join(target_path, file), values),
                    )
                else:
                    self.template_file_to_file(
                        os.path.join(templates_path, file),
                        values,
                        os.path.join(target_path, file),
                    )
            elif os.path.isdir(os.path.join(templates_path, file)):
                os.makedirs(
                    self.template_string(os.path.join(target_path, file), values),
                    exist_ok=True,
                )
                self.copy(values, os.path.join(templates_path, file))
            else:
                print(f"Skipping {file}")
