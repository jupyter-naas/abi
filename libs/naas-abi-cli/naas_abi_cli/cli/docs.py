from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Literal

import click

from naas_abi_cli.docs_builder import DocumentationAgent


_SKIP_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    "node_modules",
}

RegenerationReason = Literal["missing", "outdated"]


@dataclass
class DocSyncItem:
    source_file: Path
    target_file: Path
    reason: RegenerationReason


def _is_test_file(file_path: Path) -> bool:
    return file_path.name.endswith("_test.py") or file_path.name.startswith("test_")


def iter_python_files(source_root: Path, include_tests: bool = False) -> list[Path]:
    files: list[Path] = []
    for file_path in source_root.rglob("*.py"):
        if any(part in _SKIP_DIRECTORIES for part in file_path.parts):
            continue
        if file_path.name == "__init__.py":
            continue
        if not include_tests and _is_test_file(file_path):
            continue
        files.append(file_path)
    return sorted(files)


def target_markdown_path(
    source_file: Path, source_root: Path, output_root: Path
) -> Path:
    relative_source_path = source_file.relative_to(source_root)
    return output_root / relative_source_path.with_suffix(".md")


def needs_regeneration(
    source_file: Path, target_file: Path
) -> tuple[bool, RegenerationReason | None]:
    if not target_file.exists():
        return True, "missing"

    source_mtime = source_file.stat().st_mtime
    target_mtime = target_file.stat().st_mtime
    if target_mtime < source_mtime:
        return True, "outdated"

    return False, None


def collect_docs_to_regenerate(
    source_root: Path,
    output_root: Path,
    include_tests: bool = False,
) -> list[DocSyncItem]:
    stale_docs: list[DocSyncItem] = []
    for source_file in iter_python_files(
        source_root=source_root, include_tests=include_tests
    ):
        target_file = target_markdown_path(
            source_file=source_file,
            source_root=source_root,
            output_root=output_root,
        )
        should_regenerate, reason = needs_regeneration(source_file, target_file)
        if should_regenerate:
            assert reason is not None
            stale_docs.append(
                DocSyncItem(
                    source_file=source_file, target_file=target_file, reason=reason
                )
            )
    return stale_docs


def _parse_dotenv_key(dotenv_path: Path, key: str) -> str | None:
    if not dotenv_path.exists() or not dotenv_path.is_file():
        return None

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue

        parsed_key, parsed_value = line.split("=", 1)
        parsed_key = parsed_key.strip()
        if parsed_key != key:
            continue

        value = parsed_value.strip()
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        return value

    return None


def resolve_openai_api_key() -> str | None:
    env_value = os.getenv("OPENAI_API_KEY")
    if env_value:
        return env_value

    dotenv_value = _parse_dotenv_key(Path(".env"), "OPENAI_API_KEY")
    if dotenv_value:
        os.environ["OPENAI_API_KEY"] = dotenv_value
        return dotenv_value

    return None


def generate_documentation_for_items(
    stale_docs: list[DocSyncItem],
    model: str,
    workers: int = 10,
) -> int:
    if workers < 1:
        raise ValueError("workers must be >= 1")

    max_workers = min(workers, len(stale_docs)) if stale_docs else workers

    def _generate(item: DocSyncItem) -> None:
        documentation_agent = DocumentationAgent(model=model)
        documentation_agent.generate_and_write(
            source_file=item.source_file,
            target_file=item.target_file,
        )

    if max_workers == 1:
        for item in stale_docs:
            _generate(item)
        return len(stale_docs)

    errors: list[str] = []
    completed = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_generate, item): item for item in stale_docs}
        for future in as_completed(futures):
            item = futures[future]
            try:
                future.result()
                completed += 1
            except Exception as e:
                errors.append(f"{item.source_file}: {e}")

    if errors:
        details = "\n".join(f"- {msg}" for msg in errors[:10])
        raise RuntimeError(
            "Failed to generate documentation for one or more files:\n" + details
        )

    generated_count = 0
    generated_count += completed
    return generated_count


@click.group("docs")
def docs() -> None:
    """Documentation tooling for ABI projects."""


@docs.command("sync")
@click.option(
    "--source",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("libs/naas-abi-core/naas_abi_core"),
    show_default=True,
    help="Root folder containing Python source files.",
)
@click.option(
    "--output",
    type=click.Path(file_okay=False, path_type=Path),
    default=Path("docs/reference"),
    show_default=True,
    help="Root folder where markdown files are expected/generated.",
)
@click.option(
    "--include-tests",
    is_flag=True,
    default=False,
    help="Include Python test files in staleness checks.",
)
@click.option(
    "--fail-on-stale",
    is_flag=True,
    default=False,
    help="Exit with a non-zero status when stale docs are detected.",
)
@click.option(
    "--generate",
    is_flag=True,
    default=False,
    help="Generate/update stale documentation files using the DocumentationAgent.",
)
@click.option(
    "--model",
    type=str,
    default="gpt-5.2",
    show_default=True,
    help="LLM model ID used by the DocumentationAgent.",
)
@click.option(
    "--workers",
    type=click.IntRange(min=1),
    default=10,
    show_default=True,
    help="Number of files to generate in parallel when using --generate.",
)
def sync_docs(
    source: Path,
    output: Path,
    include_tests: bool,
    fail_on_stale: bool,
    generate: bool,
    model: str,
    workers: int,
) -> None:
    stale_docs = collect_docs_to_regenerate(
        source_root=source,
        output_root=output,
        include_tests=include_tests,
    )

    if not stale_docs:
        click.echo("Documentation is up to date.")
        return

    click.echo(f"Detected {len(stale_docs)} file(s) requiring documentation updates:")
    for item in stale_docs:
        click.echo(f"- [{item.reason}] {item.source_file} -> {item.target_file}")

    if generate:
        if resolve_openai_api_key() is None:
            raise click.ClickException(
                "OPENAI_API_KEY is required when using --generate. "
                "Set it in your environment or in a local .env file."
            )

        click.echo(
            f"Generating {len(stale_docs)} documentation file(s) with model '{model}' using up to {workers} workers..."
        )
        generated_count = generate_documentation_for_items(
            stale_docs=stale_docs,
            model=model,
            workers=workers,
        )
        click.echo(f"Generated {generated_count} documentation file(s).")
        return

    if fail_on_stale:
        raise click.ClickException(
            f"{len(stale_docs)} documentation file(s) need regeneration."
        )
