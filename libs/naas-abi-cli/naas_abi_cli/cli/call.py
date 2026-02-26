"""abi call aia — delegates to naas_aia."""

import click


@click.command("call")
@click.argument("model", default="aia")
def call(model: str):
    """Run AIA (SOUL + DuckDuckGo search)."""
    from naas_aia import run
    run(model=model.lower() or "aia")
