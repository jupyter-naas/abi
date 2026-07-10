"""Factory tests: settings-driven adapter selection."""

import pytest

from desktop.config.desktop_config import DEFAULT_SETTINGS
from desktop.harness.adapters.opencode import OpencodeHarnessAdapter
from desktop.harness.adapters.pi import PiHarnessAdapter
from desktop.harness.factory import KNOWN_HARNESSES, create_harness

_FAKE_WORKSPACE = "/tmp/ws"  # nosec B108


def test_default_settings_select_opencode() -> None:
    assert DEFAULT_SETTINGS["harness"] == "opencode"
    harness = create_harness(DEFAULT_SETTINGS)
    assert isinstance(harness, OpencodeHarnessAdapter)


def test_opencode_harness_wires_workspace_and_binary() -> None:
    harness = create_harness(
        {
            "harness": "opencode",
            "workspace_root": _FAKE_WORKSPACE,
            "opencode_bin": "/opt/bin/opencode",
        }
    )
    assert isinstance(harness, OpencodeHarnessAdapter)
    assert harness.client.workdir == _FAKE_WORKSPACE
    assert harness.client.opencode_bin == "/opt/bin/opencode"


def test_pi_harness_wires_workspace_and_binary() -> None:
    harness = create_harness(
        {"harness": "pi", "workspace_root": _FAKE_WORKSPACE, "pi_bin": "/opt/bin/pi"}
    )
    assert isinstance(harness, PiHarnessAdapter)
    assert harness.workspace_root == _FAKE_WORKSPACE
    assert harness.pi_bin == "/opt/bin/pi"


def test_missing_harness_key_defaults_to_opencode() -> None:
    harness = create_harness({"workspace_root": _FAKE_WORKSPACE})
    assert isinstance(harness, OpencodeHarnessAdapter)


def test_harness_key_is_case_insensitive() -> None:
    assert isinstance(create_harness({"harness": " Pi "}), PiHarnessAdapter)


def test_unknown_harness_raises_clear_error() -> None:
    with pytest.raises(ValueError, match="unknown harness 'claude'"):
        create_harness({"harness": "claude"})
    for name in KNOWN_HARNESSES:
        create_harness({"harness": name})
