import click

from .new import new


@new.command("module")
@click.argument("module-name")
@click.argument("module-path")
def new_module(module_name: str, module_path: str):
    pass
