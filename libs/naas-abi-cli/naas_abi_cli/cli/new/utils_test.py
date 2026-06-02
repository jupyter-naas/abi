import pytest

from naas_abi_cli.cli.new.utils import to_kebab_case, to_pascal_case, to_snake_case


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
