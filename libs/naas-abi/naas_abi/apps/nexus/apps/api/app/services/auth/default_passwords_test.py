from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.services.auth.default_passwords import (
    is_known_default_password,
)


@pytest.mark.parametrize("password", ["admin", "Admin1234!", "admin1234", "ADMIN", " admin "])
def test_shipped_default_passwords_are_recognised(password: str) -> None:
    assert is_known_default_password(password)


@pytest.mark.parametrize("password", ["", "correct horse battery staple", "Zq8-generated-Xy"])
def test_other_passwords_are_not_flagged(password: str) -> None:
    assert not is_known_default_password(password)
