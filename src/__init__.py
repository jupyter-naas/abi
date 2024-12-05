from abi.services.secret.Secret import Secret
from abi.services.secret.adaptors.secondary.dotenv_secret_secondaryadaptor import DotenvSecretSecondaryAdaptor
from src import cli

secret = Secret(DotenvSecretSecondaryAdaptor())


if __name__ == "__main__":
    cli()