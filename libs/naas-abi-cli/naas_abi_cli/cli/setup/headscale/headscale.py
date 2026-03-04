from ..setup import setup


@setup.command("headscale")
def install():
    import os

    from ...deploy.local import setup_local_deploy

    setup_local_deploy(os.getcwd(), include_headscale=True)
