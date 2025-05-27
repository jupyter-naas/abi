import click
import importlib
import yaml
from pathlib import Path


def load_config():
    """Load config.yaml and return as Python dictionary."""
    config_path = Path("config.yaml")
    if not config_path.exists():
        return {}

    with open(config_path) as f:
        return yaml.safe_load(f) or {}


@click.group()
def cli():
    pass


@cli.group()
def run():
    """Run various components"""
    pass


@run.command()
@click.option("--name", required=True, help="Name of the pipeline to run")
def pipeline(name):
    """Run a specific pipeline"""
    # Load config file
    config = load_config()

    if "pipelines" not in config:
        click.echo("Error: 'pipelines' section not found in config.yaml")
        return

    pipeline_config = None
    for pipeline in config["pipelines"]:
        if pipeline["name"] == name:
            pipeline_config = pipeline
            break

    if not pipeline_config:
        click.echo(f"Error: Pipeline '{name}' not found in config.yaml")
        return

    # Import and run pipeline
    module_path = f"src.data.pipelines.{name}"
    _ = importlib.import_module(module_path)


def main():
    cli()


if __name__ == "__main__":
    cli()
