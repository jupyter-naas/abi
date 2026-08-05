from pathlib import Path

from naas_abi.config.dotenv_secrets import write_dotenv_secret


def test_write_dotenv_secret_creates_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    env_path = tmp_path / ".env"
    write_dotenv_secret("GITHUB_ACCESS_TOKEN", "ghp_test_token")
    assert env_path.is_file()
    content = env_path.read_text(encoding="utf-8")
    assert "GITHUB_ACCESS_TOKEN=" in content
    assert "ghp_test_token" in content
