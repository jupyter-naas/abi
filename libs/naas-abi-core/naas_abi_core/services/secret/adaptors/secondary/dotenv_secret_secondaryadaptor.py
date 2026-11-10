import os
import re
import stat
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from threading import Lock
from typing import Any

from dotenv import dotenv_values, find_dotenv, set_key, unset_key
from dotenv.parser import parse_stream
from naas_abi_core.services.secret.SecretPorts import ISecretAdapter, checked_key
from naas_abi_core.utils.Logger import logger

# The names docker compose reads from a dotenv file, for interpolation and
# env_file alike (checked against compose v5.6, any character first). Any other
# name, such as ``iam/signing-keys/<id>``, makes compose refuse the whole file
# ("unexpected character "/" in variable name").
COMPOSE_NAME = re.compile(r"[A-Za-z0-9_.\[\]-]+")

SIDECAR_SUFFIX = ".sidecar"


def is_compose_name(key: str) -> bool:
    return bool(COMPOSE_NAME.fullmatch(key))


def sidecar_path_of(path: str) -> str:
    """Where the keys with other names are kept: ``.env`` -> ``.env.sidecar``."""
    return f"{path}{SIDECAR_SUFFIX}"


def move_keys_to_sidecar(path: str) -> list[str]:
    """Move the keys of the dotenv file ``path`` that compose cannot read to
    its sidecar, and return their names.

    Repairs a ``.env`` an earlier engine wrote its own keys into, which docker
    compose then refused. Each file is rewritten once, the sidecar first, and
    the lines move as they are. Values are never logged.
    """
    sidecar = sidecar_path_of(path)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as source:
        bindings = list(parse_stream(source))
    moved = [
        binding
        for binding in bindings
        if binding.key is not None and not is_compose_name(binding.key)
    ]
    if not moved:
        return []
    names = {binding.key for binding in moved}

    kept_in_sidecar = []
    if os.path.exists(sidecar):
        with open(sidecar, encoding="utf-8") as source:
            kept_in_sidecar = [
                binding.original.string
                for binding in parse_stream(source)
                if binding.key not in names
            ]
    _rewrite(
        sidecar,
        _joined(kept_in_sidecar + [binding.original.string for binding in moved]),
        owner_of=path,
    )
    _rewrite(
        path,
        _joined(
            [
                binding.original.string
                for binding in bindings
                if binding.key not in names
            ]
        ),
        owner_of=path,
    )
    logger.warning(
        f"Moved {len(names)} secret(s) docker compose cannot read from {path} "
        f"to {sidecar}: {', '.join(sorted(str(name) for name in names))}"
    )
    return sorted(str(name) for name in names)


def _joined(lines: list[str]) -> str:
    return "".join(line if line.endswith("\n") else f"{line}\n" for line in lines)


def _rewrite(path: str, content: str, owner_of: str) -> None:
    """Replace ``path`` with ``content`` in one rename. It keeps its mode (a new
    file is readable by its owner only) and gets the owner of ``owner_of``."""
    try:
        mode: int | None = stat.S_IMODE(os.stat(path).st_mode)
    except FileNotFoundError:
        mode = None
    descriptor, temporary = tempfile.mkstemp(
        prefix=".tmp_", dir=os.path.dirname(os.path.abspath(path))
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as destination:
            destination.write(content)
        if mode is not None:
            os.chmod(temporary, mode)
        os.replace(temporary, path)
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise
    _give_owner(path, owner_of)


def _give_owner(path: str, owner_of: str) -> None:
    try:
        owner, current = os.stat(owner_of), os.stat(path)
        if (current.st_uid, current.st_gid) != (owner.st_uid, owner.st_gid):
            os.chown(path, owner.st_uid, owner.st_gid)
    except OSError as exc:
        logger.warning(f"Could not give {path} the owner of {owner_of}: {exc}")


@contextmanager
def _keep_owner(path: str, owner_of: str | None = None) -> Iterator[None]:
    """python-dotenv rewrites the file through a new one. Give it back the
    old file's owner (or, for a file it creates, the owner of ``owner_of``):
    a container running as root must not leave the project's bind-mounted
    files unwritable for its user."""
    try:
        before = os.stat(path)
    except OSError:
        yield
        if owner_of is not None and os.path.exists(path):
            _give_owner(path, owner_of)
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

    The file holds only names docker compose reads (``COMPOSE_NAME``): compose
    reads the project's ``.env`` too, and refuses all of it over one other
    name. Other keys, such as the ones the engine keeps for itself
    (``iam/signing-keys/<id>``, ``idp/code-key``), go to the sidecar
    ``<path>.sidecar``, readable by its owner only. Reads cover both files.

    Opening the adapter never writes. ``move_keys_to_sidecar`` repairs a file
    an earlier version wrote such keys into; the secret service's
    configuration runs it before opening a writable adapter.

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
    ):
        self.path = path
        self.sidecar_path = sidecar_path_of(path)
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
            if is_compose_name(key):
                os.environ[key] = value
                with _keep_owner(self.path):
                    set_key(self.path, key, value)
            else:
                # Kept out of os.environ too, which child processes inherit.
                # set_key creates a missing sidecar in one rename, mode 0600.
                with _keep_owner(self.sidecar_path, owner_of=self.path):
                    set_key(self.sidecar_path, key, value)
            self.secrets[key] = value

    def remove(self, key: str):
        checked_key(key)
        if self.read_only:
            self._skip_write("remove", key)
            return
        with self._lock:
            if is_compose_name(key):
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
