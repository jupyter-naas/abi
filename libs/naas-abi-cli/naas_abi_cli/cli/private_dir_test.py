import subprocess
from pathlib import Path

from naas_abi_cli.cli.deploy.local import BACKUP_DIRECTORY, setup_local_deploy
from naas_abi_cli.cli.private_dir import keep_out_of_git


def _git(project: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=project, check=True, capture_output=True, text=True
    ).stdout


def test_a_private_directory_ignores_itself(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    private = tmp_path / ".snapshots"
    (private / "20261019").mkdir(parents=True)
    (private / "20261019" / "volume.tar.gz").write_text("data")

    keep_out_of_git(private)

    assert _git(tmp_path, "status", "--porcelain") == ""


def test_an_existing_gitignore_in_it_is_left_alone(tmp_path: Path) -> None:
    private = tmp_path / ".snapshots"
    private.mkdir()
    (private / ".gitignore").write_text("keep.txt\n")

    keep_out_of_git(private)

    assert (private / ".gitignore").read_text() == "keep.txt\n"


def test_a_regenerate_backup_of_the_env_file_stays_out_of_git(tmp_path: Path) -> None:
    # The backup copies .env, with every secret of the project.
    setup_local_deploy(str(tmp_path), base_domain="localhost", nats=True)
    _git(tmp_path, "init", "-q")
    (tmp_path / ".gitignore").write_text("")
    setup_local_deploy(
        str(tmp_path), base_domain="localhost", nats=True, regenerate=True
    )

    backups = tmp_path / BACKUP_DIRECTORY
    assert list(backups.rglob(".env"))
    untracked = _git(tmp_path, "status", "--porcelain", "--untracked-files=all")
    assert ".abi-backups" not in untracked


def test_private_file_keeps_owner_only_under_a_wide_umask(tmp_path: Path) -> None:
    import os
    import stat

    from naas_abi_cli.cli.private_dir import private_directory, private_file

    previous = os.umask(0o022)
    try:
        created = tmp_path / ".env"
        private_file(created)
        existing = tmp_path / ".env.old"
        existing.write_text("KEY=value\n")
        private_file(existing)
        folder = tmp_path / "a" / "b"
        private_directory(folder)
    finally:
        os.umask(previous)
    assert stat.S_IMODE(created.stat().st_mode) == 0o600
    assert stat.S_IMODE(existing.stat().st_mode) == 0o600
    assert existing.read_text() == "KEY=value\n"
    assert stat.S_IMODE(folder.stat().st_mode) == 0o700


def test_local_deploy_keeps_env_and_its_backups_private(tmp_path: Path) -> None:
    import os
    import stat

    previous = os.umask(0o022)
    try:
        setup_local_deploy(str(tmp_path), base_domain="localhost", nats=True)
        setup_local_deploy(
            str(tmp_path), base_domain="localhost", nats=True, regenerate=True
        )
    finally:
        os.umask(previous)
    assert stat.S_IMODE((tmp_path / ".env").stat().st_mode) == 0o600
    (backup,) = (tmp_path / BACKUP_DIRECTORY).glob("*/.env")
    assert stat.S_IMODE(backup.stat().st_mode) == 0o600
    for folder in (backup.parent, backup.parent.parent, backup.parent.parent.parent):
        assert stat.S_IMODE(folder.stat().st_mode) == 0o700


def test_private_file_keeps_going_on_another_users_file(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    import os

    from naas_abi_cli.cli.private_dir import private_file

    target = tmp_path / ".env"
    target.write_text("KEY=value\n")

    def refuse(*_args, **_kwargs):
        raise PermissionError(1, "Operation not permitted")

    monkeypatch.setattr(os, "chmod", refuse)
    private_file(target)  # no traceback: a warning
    assert "belongs to another user" in capsys.readouterr().err
    assert target.read_text() == "KEY=value\n"
