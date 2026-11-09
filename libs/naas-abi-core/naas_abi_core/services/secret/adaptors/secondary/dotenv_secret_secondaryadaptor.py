import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from threading import Lock
from typing import Any

from dotenv import dotenv_values, find_dotenv, set_key, unset_key
from naas_abi_core.services.secret.SecretPorts import ISecretAdapter, checked_key
from naas_abi_core.utils.Logger import logger

# The names every reader of a dotenv file takes: docker compose (interpolation
# and env_file), shells, `abi deploy local`. A name outside it, such as
# ``iam/signing-keys/<id>``, makes compose refuse the whole file ("unexpected
# character "/" in variable name").
DOTENV_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]*")

SIDECAR_SUFFIX = ".sidecar"


def is_dotenv_name(key: str) -> bool:
    return bool(DOTENV_NAME.fullmatch(key))


def sidecar_path_of(path: str) -> str:
    """Where the keys with other names go: ``.env`` -> ``.env.sidecar``."""
    return f"{path}{SIDECAR_SUFFIX}"


def move_keys_to_sidecar(path: str, sidecar_path: str | None = None) -> list[str]:
    """Move the keys of ``path`` that are not dotenv names to its sidecar.

    Repairs a ``.env`` an earlier engine wrote them into, which docker compose
    then refused. Returns the names moved; values are never logged.
    """
    sidecar = sidecar_path or sidecar_path_of(path)
    if not os.path.exists(path):
        return []
    values = dotenv_values(path, interpolate=False)
    moved = [
        key
        for key, value in values.items()
        if value is not None and not is_dotenv_name(key)
    ]
    if not moved:
        return []
    _create_like(sidecar, path)
    for key in moved:
        with _keep_owner(sidecar):
            set_key(sidecar, key, str(values[key]))
    for key in moved:
        with _keep_owner(path):
            unset_key(path, key)
    logger.warning(
        f"Moved {len(moved)} secret(s) from {path} to {sidecar}, where names "
        f"docker compose cannot read are kept: {', '.join(moved)}"
    )
    return moved


def _create_like(path: str, like: str) -> None:
    """Create ``path`` empty, readable by its owner only, owned as ``like``."""
    if os.path.exists(path):
        return
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    os.close(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
    try:
        owner = os.stat(like)
        os.chown(path, owner.st_uid, owner.st_gid)
    except OSError as exc:
        logger.warning(f"Could not give {path} the owner of {like}: {exc}")


@contextmanager
def _keep_owner(path: str) -> Iterator[None]:
    """python-dotenv rewrites the file through a new one. Give it back the
    old file's owner: a container running as root must not leave the
    project's bind-mounted .env unwritable for its user."""
    try:
        before = os.stat(path)
    except OSError:
        yield
        return
    yield
    try:
        after = os.stat(path)
        if (after.st_uid, after.st_gid) != (before.st_uid, before.st_gid):
            os.chown(path, before.st_uid, before.st_gid)
    except OSError as exc:
        logger.warning(f"Could not restore the owner of {path}: {exc}")


class DotenvSecretSecondaryAdaptor(ISecretAdapter):
    """Secrets in a dotenv file.

    The file holds only names every dotenv reader takes (``DOTENV_NAME``).
    Others, such as the keys the engine keeps for itself
    (``iam/signing-keys/<id>``, ``idp/code-key``), go to a sidecar file,
    ``<path>.sidecar`` unless ``sidecar_path`` says otherwise: docker compose
    reads the project's ``.env`` too, and refuses it with such a name in it.
    Keys an earlier version wrote into the file are moved to the sidecar when
    the adapter opens it.

    ``read_only`` serves a file another process owns, such as one on a volume
    mounted read-only: ``set`` and ``remove`` leave it alone, so the service
    can still write to its other adapters.

    Reads take the file first, then the process environment.
    ``environment_first`` reverses that, so a variable the deployment sets wins
    over a value saved in the file earlier, as when the config is rendered;
    ``list`` shows the same values for the file's keys.
    """

    def __init__(
        self,
        path: str = ".env",
        read_only: bool = False,
        environment_first: bool = False,
        sidecar_path: str | None = None,
    ):
        self.path = path
        self.sidecar_path = sidecar_path or sidecar_path_of(path)
        self.read_only = read_only
        self.environment_first = environment_first
        self._lock = Lock()

        if not os.path.exists(self.path):
            raise FileNotFoundError(
                "Dotenv secret adapter is configured to use "
                f"'{self.path}', but this file does not exist. "
                "Please create it or update services.secret.secret_adapters[].config.path."
            )

        logger.debug(f"dotenv is using the file: {self.path}")
        logger.debug(f"dotenv discoverable file is: {find_dotenv()}")

        if not self.read_only:
            move_keys_to_sidecar(self.path, self.sidecar_path)
        self.secrets = dotenv_values(self.path)
        if os.path.exists(self.sidecar_path):
            self.secrets.update(dotenv_values(self.sidecar_path, interpolate=False))

    def get(self, key: str, default: Any = None) -> str | Any | None:
        with self._lock:
            env_value = os.environ.get(key)
            if self.environment_first and env_value is not None:
                return env_value

            secret_value = self.secrets.get(key)
            if secret_value is not None:
                return str(secret_value)

            if env_value is not None:
                return env_value

        return default

    def set(self, key: str, value: str):
        checked_key(key)
        if self.read_only:
            self._skip_write("set", key)
            return
        with self._lock:
            if is_dotenv_name(key):
                os.environ[key] = value
                path = self.path
            else:
                # Not an environment variable either: kept out of os.environ,
                # which child processes inherit.
                path = self.sidecar_path
                _create_like(path, self.path)
            with _keep_owner(path):
                set_key(path, key, value)
            self.secrets[key] = value

    def remove(self, key: str):
        checked_key(key)
        if self.read_only:
            self._skip_write("remove", key)
            return
        with self._lock:
            if is_dotenv_name(key):
                with _keep_owner(self.path):
                    unset_key(self.path, key)
            elif os.path.exists(self.sidecar_path):
                with _keep_owner(self.sidecar_path):
                    unset_key(self.sidecar_path, key)
            self.secrets.pop(key, None)
            os.environ.pop(key, None)

    def _skip_write(self, operation: str, key: str) -> None:
        if key in self.secrets:
            # The value in this file still answers reads that no earlier
            # adapter answers.
            logger.warning(
                f"Secret {key} is in the read-only file {self.path}: {operation} "
                "does not change it there."
            )

    def list(self) -> dict[str, str | None]:
        with self._lock:
            secrets: dict[str, str | None] = {}
            for key in self.secrets:
                value = self.secrets.get(key)
                if self.environment_first and key in os.environ:
                    value = os.environ[key]
                secrets[str(key)] = str(value)
            return secrets
