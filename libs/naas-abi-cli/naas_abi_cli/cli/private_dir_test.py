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
