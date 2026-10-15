from pathlib import Path

import pytest

from naas_abi_cli.cli.new.utils import (
    module_package_name,
    to_kebab_case,
    to_pascal_case,
    to_snake_case,
)


@pytest.mark.parametrize(
    "given,expected",
    [
        ("my-test-app", "MyTestApp"),
        ("my_test_app", "MyTestApp"),
        ("my test app", "MyTestApp"),
        ("MyTestApp", "MyTestApp"),
        ("myTestApp", "MyTestApp"),
        ("api2Server", "Api2Server"),
        ("", ""),
        ("single", "Single"),
    ],
)
def test_to_pascal_case_is_idempotent(given: str, expected: str) -> None:
    assert to_pascal_case(given) == expected
    assert to_pascal_case(to_pascal_case(given)) == expected


@pytest.mark.parametrize(
    "given,expected",
    [
        ("my-test-app", "my_test_app"),
        ("my_test_app", "my_test_app"),
        ("MyTestApp", "my_test_app"),
        ("myTestApp", "my_test_app"),
        ("", ""),
    ],
)
def test_to_snake_case_is_idempotent(given: str, expected: str) -> None:
    assert to_snake_case(given) == expected
    assert to_snake_case(to_snake_case(given)) == expected


@pytest.mark.parametrize(
    "given,expected",
    [
        ("my-test-app", "my-test-app"),
        ("my_test_app", "my-test-app"),
        ("MyTestApp", "my-test-app"),
        ("myTestApp", "my-test-app"),
        ("", ""),
    ],
)
def test_to_kebab_case_is_idempotent(given: str, expected: str) -> None:
    assert to_kebab_case(given) == expected
    assert to_kebab_case(to_kebab_case(given)) == expected


def _package(folder: Path, body: str = "") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "__init__.py").write_text(body)
    return folder


def test_module_package_name_finds_the_module_from_any_folder_in_it(
    tmp_path: Path,
) -> None:
    core = _package(tmp_path / "src" / "core")
    research = _package(core / "research", "class ABIModule(BaseModule):\n    pass\n")
    _package(research / "agents")
    _package(research / "apps" / "reports")

    for start in (
        research,
        research / "agents",
        research / "apps",
        research / "apps" / "reports",
        research / "apps" / "new_app",  # not created yet
    ):
        assert module_package_name(start) == "core.research"


def test_module_package_name_without_an_abi_module(tmp_path: Path) -> None:
    plain = _package(tmp_path / "src" / "plain")
    assert module_package_name(plain / "agents") == "plain"
    assert module_package_name(tmp_path / "loose") is None


def test_only_a_class_definition_makes_a_module(tmp_path: Path) -> None:
    research = _package(
        tmp_path / "src" / "research", "class ABIModule(BaseModule):\n    pass\n"
    )
    support = _package(
        research / "support",
        '"""class ABIModule lives in the parent."""\n'
        "# class ABIModule\n"
        "class ABIModuleConfiguration:\n    pass\n",
    )

    assert module_package_name(support / "agents") == "research"


def test_an_unreadable_package_above_the_project_is_passed_over(tmp_path: Path) -> None:
    # No package defines ABIModule, so the walk reads every __init__.py up.
    (tmp_path / "__init__.py").write_bytes(b"\xff\xfe not utf-8")
    plain = _package(tmp_path / "src" / "plain")

    assert module_package_name(plain / "apps") == "plain"


def test_the_name_starts_below_src_even_when_src_is_a_package(tmp_path: Path) -> None:
    src = _package(tmp_path / "src")
    core = _package(src / "core")
    research = _package(core / "research", "class ABIModule:\n    pass\n")

    assert module_package_name(research / "agents") == "core.research"
