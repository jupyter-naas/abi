from ..setup import setup


@setup.command("headscale")
def install():
    import os

    import naas_abi_cli
    from naas_abi_cli.cli.utils.Copier import Copier

    copier = Copier(
        templates_path=os.path.join(
            os.path.dirname(naas_abi_cli.__file__), "cli/setup/headscale/templates"
        ),
        destination_path=os.path.join(os.getcwd(), ".headscale"),
    )
    copier.copy(values={})
