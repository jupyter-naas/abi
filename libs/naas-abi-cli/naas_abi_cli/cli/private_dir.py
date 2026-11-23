import os
import sys
from pathlib import Path


def keep_out_of_git(directory: Path) -> None:
    """Make ``directory`` ignore itself, whatever the project's .gitignore says.

    For folders the CLI fills with copies of `.env` or with volume archives: a
    project created before the CLI ignored them would commit its secrets with
    `git add -A`.
    """
    gitignore = directory / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*\n", encoding="utf-8")


def private_file(path: str | os.PathLike[str]) -> None:
    """Create ``path`` readable and writable by its owner only, or make it so.

    For files that hold secrets (`.env`, its copies, sign-in mails): created
    0600 whatever the umask, so they never exist readable by other users, and
    later writes keep the mode.
    """
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    os.close(descriptor)
    try:
        os.chmod(path, 0o600)
    except PermissionError:
        # Writable but another user's (one a container created as root): left
        # as is, and said so.
        print(
            f"Warning: {path} belongs to another user, so its mode stays as it is. "
            f"Make it yours to keep it private: sudo chown {os.getuid()}:{os.getgid()} {path}",
            file=sys.stderr,
        )


def private_directory(path: str | os.PathLike[str]) -> None:
    """Create ``path`` (and its parents) and make it reachable by its owner only."""
    Path(path).mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except PermissionError:
        # Another user's folder (one a container created as root): left as is.
        pass


def is_secret_file(name: str) -> bool:
    """Whether a file name is a dotenv file that holds values (`.env`,
    `.env.dokploy`, ...), not an example."""
    base = os.path.basename(name)
    return (base == ".env" or base.startswith(".env.")) and not base.endswith(
        ".example"
    )
