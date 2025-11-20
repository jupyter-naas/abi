import os

import click


@click.command("init")
@click.argument("path")
def init(path: str):
    if path == ".":
        path = os.getcwd()

    os.makedirs(path, exist_ok=True)
    os.exec(f"cd {path} && uv init .")
