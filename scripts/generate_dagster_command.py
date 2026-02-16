import glob
import os
import sys


def _sanitize_module_path(def_path: str) -> str:
    """Convert a python file path to a module path for the dagster CLI."""

    return def_path.replace("/", ".").replace("\\", ".").removesuffix(".py")


dagster_home = os.environ.get("DAGSTER_HOME", "/app/.dagster")
instance_config_path = os.path.join(dagster_home, "dagster.yaml")

command = "uv run dagster dev --host 0.0.0.0 --port 3000"

if not os.path.exists(instance_config_path):
    print(
        f"[dagster] Warning: instance config not found at {instance_config_path};"
        " falling back to defaults.",
        file=sys.stderr,
    )

definition_files = sorted(
    glob.glob("src/**/orchestration/definitions.py", recursive=True)
)

for definition_file in definition_files:
    command += f" -m {_sanitize_module_path(definition_file)}"

print(command)
