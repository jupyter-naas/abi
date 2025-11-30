import click


@click.group("new")
def new():
    pass


@new.command("module")
@click.argument("module-name")
@click.argument("module-path")
def new_module(module_name: str, module_path: str):
    print(f"Creating a new module: {module_name} at {module_path}")
