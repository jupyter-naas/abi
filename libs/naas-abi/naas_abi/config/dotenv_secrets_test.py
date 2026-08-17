from pathlib import Path

from naas_abi.config.dotenv_secrets import (
    clear_dotenv_secret,
    is_usable_secret_value,
    write_dotenv_secret,
)


def test_write_dotenv_secret_creates_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    env_path = tmp_path / ".env"
    write_dotenv_secret("GITHUB_ACCESS_TOKEN", "ghp_test_token")
    assert env_path.is_file()
    content = env_path.read_text(encoding="utf-8")
    assert "GITHUB_ACCESS_TOKEN=" in content
    assert "ghp_test_token" in content


def test_clear_dotenv_secret_removes_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    write_dotenv_secret("GITHUB_ACCESS_TOKEN", "ghp_test_token")
    clear_dotenv_secret("GITHUB_ACCESS_TOKEN")
    content = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "GITHUB_ACCESS_TOKEN" not in content


def test_is_usable_secret_value_rejects_placeholders() -> None:
    assert is_usable_secret_value("ghp_real_token_value_here") is True
    assert is_usable_secret_value("your-github-token-here") is False
    assert is_usable_secret_value("placeholder") is False
    assert is_usable_secret_value("") is False
