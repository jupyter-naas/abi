import click
from naas_abi_core.engine.Engine import Engine


@click.group("run")
def run():
    pass


@run.command(
    "script",
    context_settings={
        "ignore_unknown_options": True,
        "allow_extra_args": True,
    },
)
@click.pass_context
@click.argument("path", type=str, required=True)
def run_script(ctx: click.Context, path: str):
    click.echo(f"[abi run script] Loading engine for: {path}")
    engine = Engine()
    engine.load()
    click.echo("[abi run script] Engine loaded. Running script...")

    import runpy
    import sys

    # Forward any arguments after the script path to the target script so
    # argparse/click inside the script can parse them.
    script_args = list(ctx.args)
    sys.argv = [path, *script_args]
    runpy.run_path(path, run_name="__main__")
