import click
from naas_abi_core.engine.Engine import Engine


@click.group("run")
def run():
    pass


@run.command("script")
@click.argument("path", type=str, required=True)
def run_script(path: str):
    engine = Engine()
    engine.load()

    import runpy

    runpy.run_path(path, run_name="__main__")
