"""Dagster and RabbitMQ, the legacy extras of naas-abi-core.

A project without NATS (no ``nats:`` block in its config) schedules module
orchestrations with Dagster and can run its bus on RabbitMQ. NATS mode replaces
both, with module jobs and the JetStream bus, so naas-abi-core no longer
installs them: a project that still uses them installs
``naas-abi-core[dagster,rabbitmq]``. They are legacy, to be removed in the next
major.

The code that imports Dagster or pika goes through ``raise_missing_extra`` so a
missing extra reads as an install hint instead of a bare ``ImportError``.
"""

import importlib.util
from typing import NoReturn

LEGACY_NOTICE = (
    "Dagster and RabbitMQ are legacy, for projects without NATS, and will be "
    "removed in the next major: NATS projects use module jobs and the JetStream "
    "bus instead."
)


# The top-level package each legacy extra installs: the extra is missing when
# this package is.
_EXTRA_PACKAGES = {"dagster": "dagster", "rabbitmq": "pika"}


def legacy_extra_of(error: ImportError) -> str | None:
    """The legacy extra missing behind ``error``: it reports one of the extra's
    modules missing and the extra's top-level package is not installed.

    With Dagster installed, a missing ``dagster.*`` submodule (a private import
    a Dagster upgrade removed) or ``dagster_*`` package is a plain missing
    module, not a missing extra.
    """
    root = (getattr(error, "name", None) or "").split(".")[0]
    if root == "dagster" or root.startswith("dagster_"):
        extra = "dagster"
    elif root == "pika":
        extra = "rabbitmq"
    else:
        return None
    if importlib.util.find_spec(_EXTRA_PACKAGES[extra]) is not None:
        return None
    return extra


def install_hint(extra: str) -> str:
    return (
        f"Install the legacy `{extra}` extra: uv add 'naas-abi-core[{extra}]' "
        f"(or pip install 'naas-abi-core[{extra}]')."
    )


class MissingLegacyExtra(ModuleNotFoundError):
    """A feature needs a legacy extra that is not installed. Keeps the missing
    module's ``name``, so ``legacy_extra_of`` recognises it as well."""

    def __init__(self, extra: str, feature: str, name: str | None):
        self.extra = extra
        super().__init__(
            f"{feature} needs the `{extra}` extra of naas-abi-core, which is not "
            f"installed. {install_hint(extra)} {LEGACY_NOTICE}",
            name=name,
        )


def raise_missing_extra(error: ModuleNotFoundError, feature: str) -> NoReturn:
    """Re-raise ``error`` with an install hint when it is a legacy extra's
    module that is missing; any other missing module is raised as is."""
    extra = legacy_extra_of(error)
    if extra is None:
        raise error
    raise MissingLegacyExtra(extra, feature, error.name) from error
