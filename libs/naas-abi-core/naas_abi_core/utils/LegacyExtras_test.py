"""Install hints when the legacy Dagster and RabbitMQ extras are missing."""

import importlib
import sys

import pytest
from naas_abi_core.utils.LegacyExtras import (
    MissingLegacyExtra,
    legacy_extra_of,
    raise_missing_extra,
)

RABBITMQ_ADAPTER = "naas_abi_core.services.bus.adapters.secondary.RabbitMQAdapter"
DAGSTER_APP = "naas_abi_core.apps.dagster.dagster"


@pytest.mark.parametrize(
    ("name", "extra"),
    [
        ("dagster", "dagster"),
        ("dagster._core.storage", "dagster"),
        ("dagster_aws.s3", "dagster"),
        ("pika", "rabbitmq"),
        ("pikachu", None),
        ("dagsterish", None),
        ("nats", None),
        (None, None),
    ],
)
def test_legacy_extra_of_when_the_extra_is_missing(monkeypatch, name, extra) -> None:
    monkeypatch.setitem(sys.modules, "dagster", None)
    monkeypatch.setitem(sys.modules, "pika", None)

    assert legacy_extra_of(ModuleNotFoundError("missing", name=name)) == extra


@pytest.mark.parametrize(
    "name",
    ["dagster._core.definitions.removed_in_an_upgrade", "dagster_something"],
)
def test_with_dagster_installed_a_missing_dagster_module_is_no_missing_extra(
    name,
) -> None:
    """A stale private import or a package of the user's own fails as itself,
    instead of asking to install an extra that is there."""
    pytest.importorskip("dagster")

    assert legacy_extra_of(ModuleNotFoundError("missing", name=name)) is None


def test_with_pika_installed_pika_is_no_missing_extra() -> None:
    pytest.importorskip("pika")

    assert legacy_extra_of(ModuleNotFoundError("missing", name="pika.spec")) is None


def test_a_missing_legacy_module_reads_as_an_install_hint(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "pika", None)

    with pytest.raises(MissingLegacyExtra) as raised:
        raise_missing_extra(ModuleNotFoundError("no", name="pika"), "The thing")

    error = raised.value
    assert error.extra == "rabbitmq"
    assert error.name == "pika"
    assert "The thing needs the `rabbitmq` extra" in str(error)
    assert "uv add 'naas-abi-core[rabbitmq]'" in str(error)
    assert "legacy" in str(error)
    # Still an ImportError for callers that catch those, and still recognised.
    assert isinstance(error, ImportError)
    assert legacy_extra_of(error) == "rabbitmq"


def test_another_missing_module_is_raised_as_is() -> None:
    original = ModuleNotFoundError("no", name="nats")
    with pytest.raises(ModuleNotFoundError) as raised:
        raise_missing_extra(original, "The thing")
    assert raised.value is original


@pytest.fixture
def without(monkeypatch):
    """Hide a top-level package, as in an install without its extra."""

    def hide(package: str, *reimported: str) -> None:
        monkeypatch.setitem(sys.modules, package, None)
        for module in reimported:
            # Imported again under the hidden package; restored afterwards.
            if module in sys.modules:
                monkeypatch.delitem(sys.modules, module)

    return hide


def test_dagster_orchestration_imports_without_dagster_and_new_says_what_to_install(
    without,
) -> None:
    from naas_abi_core.orchestrations.DagsterOrchestration import (
        DagsterOrchestration,
    )

    without("dagster")

    with pytest.raises(MissingLegacyExtra, match=r"naas-abi-core\[dagster\]"):
        DagsterOrchestration.New()


def test_dagster_orchestration_new_with_dagster() -> None:
    dagster = pytest.importorskip("dagster")
    from naas_abi_core.orchestrations.DagsterOrchestration import (
        DagsterOrchestration,
    )

    assert isinstance(DagsterOrchestration.New().definitions, dagster.Definitions)


def test_rabbitmq_adapter_without_pika_says_what_to_install(without) -> None:
    without("pika", RABBITMQ_ADAPTER)

    with pytest.raises(MissingLegacyExtra, match=r"naas-abi-core\[rabbitmq\]"):
        importlib.import_module(RABBITMQ_ADAPTER)


def test_dagster_app_without_dagster_says_what_to_install(without) -> None:
    # Raised before the app builds its engine.
    without("dagster", DAGSTER_APP)

    with pytest.raises(MissingLegacyExtra, match=r"naas-abi-core\[dagster\]"):
        importlib.import_module(DAGSTER_APP)
