from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path

import pytest

from naas_abi_cli.cli.dev_mail import latest_sign_in_code


def _mail(directory: Path, name: str, *, to: str, subject: str, body: str) -> None:
    message = EmailMessage()
    message["To"] = to
    message["From"] = "no-reply@abi.local"
    message["Subject"] = subject
    message.set_content(body)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}.eml").write_bytes(bytes(message))


def test_the_newest_code_sent_to_the_address_is_found(tmp_path: Path) -> None:
    _mail(
        tmp_path,
        "1000-a",
        to="admin@example.com",
        subject="Your ABI sign-in code",
        body="Your ABI sign-in code is: 111111\n\nEnter this code.",
    )
    _mail(
        tmp_path,
        "2000-b",
        to="admin@example.com",
        subject="Your ABI sign-in code",
        body="Your ABI sign-in code is: 222222\n\nEnter this code.",
    )
    _mail(
        tmp_path,
        "3000-c",
        to="bob@example.com",
        subject="Your ABI sign-in code",
        body="Your ABI sign-in code is: 333333\n",
    )

    found = latest_sign_in_code(tmp_path, "admin@example.com")

    assert found is not None and found.code == "222222"
    assert found.to == "admin@example.com"
    assert latest_sign_in_code(tmp_path, "Bob@Example.com").code == "333333"  # type: ignore[union-attr]


def test_without_an_address_the_newest_code_of_anyone_is_found(tmp_path: Path) -> None:
    _mail(
        tmp_path,
        "1000-a",
        to="admin@example.com",
        subject="Your ABI sign-in code",
        body="Your ABI sign-in code is: 111111\n",
    )
    _mail(
        tmp_path,
        "2000-b",
        to="bob@example.com",
        subject="Your ABI sign-in code",
        body="Your ABI sign-in code is: 333333\n",
    )

    assert latest_sign_in_code(tmp_path, None).to == "bob@example.com"  # type: ignore[union-attr]


def test_a_mail_that_is_not_a_sign_in_code_is_not_one(tmp_path: Path) -> None:
    _mail(
        tmp_path,
        "1000-a",
        to="admin@example.com",
        subject="You are invited to ABI",
        body="Ada invited you. Order 123456 shipped. Sign in: https://x.test/auth/login\n",
    )

    assert latest_sign_in_code(tmp_path, "admin@example.com") is None


@pytest.mark.parametrize("directory", ["missing", "empty"])
def test_no_mail_no_code(tmp_path: Path, directory: str) -> None:
    folder = tmp_path / directory
    if directory == "empty":
        folder.mkdir()
    assert latest_sign_in_code(folder, None) is None


def test_a_broken_file_is_skipped(tmp_path: Path) -> None:
    (tmp_path / "9000-z.eml").write_bytes(b"\xff\xfe not a message")
    _mail(
        tmp_path,
        "1000-a",
        to="admin@example.com",
        subject="Your ABI sign-in code",
        body="Your ABI sign-in code is: 111111\n",
    )

    assert latest_sign_in_code(tmp_path, "admin@example.com").code == "111111"  # type: ignore[union-attr]
