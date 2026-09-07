import os

import pytest

from naas_abi_cli.cli.new.module import new_module


@pytest.mark.parametrize(
    "given_path,expected_namespace",
    [
        # Default: the module is created directly under the current directory.
        (".", "my_test_module"),
        # Explicit relative path: separators become dots.
        (os.path.join("src", "custom", "modules"), "src.custom.modules.my_test_module"),
        # A leading "./" must not leak into the namespace.
        (os.path.join(".", "src", "modules"), "src.modules.my_test_module"),
    ],
)
def test_new_module_prints_importable_namespace(
    tmp_path,
    monkeypatch,
    capsys,
    given_path: str,
    expected_namespace: str,
) -> None:
    """The config.yaml hint must show a dotted, importable module namespace.

    The namespace is derived from the destination path relative to the current
    working directory, so an absolute path never leaks into the output.
    """
    monkeypatch.chdir(tmp_path)

    new_module("my-test-module", given_path)

    stdout = capsys.readouterr().out
    assert f"  - module: {expected_namespace}" in stdout
    # A filesystem separator in the namespace means the path was not converted.
    assert f"  - module: {expected_namespace}{os.sep}" not in stdout


def test_new_module_quiet_prints_nothing(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    new_module("my-test-module", ".", quiet=True)

    assert capsys.readouterr().out == ""
