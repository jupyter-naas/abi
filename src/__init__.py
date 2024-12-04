from abi.services.secret.Secret import Secret
from abi.services.secret.adaptors.secondary.dotenv_secret_secondaryadaptor import DotenvSecretSecondaryAdaptor

secret = Secret(DotenvSecretSecondaryAdaptor())

from cli import cli

if __name__ == "__main__":
    cli()