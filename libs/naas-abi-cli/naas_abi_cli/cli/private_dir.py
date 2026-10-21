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
