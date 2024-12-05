import click
import importlib
import yaml
from pathlib import Path

@click.group()
def cli():
    pass

@cli.group()
def run():
    """Run various components"""
    pass

@run.command()
@click.option('--name', required=True, help='Name of the pipeline to run')
def pipeline(name):
    """Run a specific pipeline"""
    # Load config file
    config_path = Path('config.yaml')
    if not config_path.exists():
        click.echo("Error: config.yaml not found")
        return

    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Find pipeline configuration
    pipeline_config = None
    for p in config.get('pipelines', []):
        if p.get('name') == name:
            pipeline_config = p
            break

    if not pipeline_config:
        click.echo(f"Error: Pipeline '{name}' not found in config.yaml")
        return

    # Import and run pipeline
    try:
        module_path = f"src.data.pipelines.{name}"
        module = importlib.import_module(module_path)
        
        # Get the pipeline class (assumed to be the last part of the name)
        class_name = ''.join(word.capitalize() for word in name.split('.')[-1].split('_'))
        pipeline_class = getattr(module, class_name)
        
        # Initialize and run pipeline with config parameters
        pipeline = pipeline_class(**pipeline_config.get('parameters', {}))
        result = pipeline.run()
        
        click.echo(f"Pipeline '{name}' completed successfully")
        click.echo(result.serialize(format="turtle"))
        
    except Exception as e:
        click.echo(f"Error running pipeline '{name}': {str(e)}")

def main():
    cli()

if __name__ == '__main__':
    cli()
