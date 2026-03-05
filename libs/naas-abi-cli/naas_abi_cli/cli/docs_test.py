from pathlib import Path
import importlib

import pytest
from click.testing import CliRunner

from naas_abi_cli.cli.docs import (
    DocSyncItem,
    _parse_dotenv_key,
    collect_docs_to_regenerate,
    docs,
    generate_documentation_for_items,
    resolve_openai_api_key,
    target_markdown_path,
)


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_collect_docs_to_regenerate_flags_missing_markdown(tmp_path: Path) -> None:
    source_root = tmp_path / "src"
    output_root = tmp_path / "docs"

    source_file = source_root / "pkg" / "Service.py"
    _write(source_file, "class Service: ...\n")

    stale = collect_docs_to_regenerate(source_root=source_root, output_root=output_root)

    assert len(stale) == 1
    assert stale[0].source_file == source_file
    assert stale[0].target_file == output_root / "pkg" / "Service.md"
    assert stale[0].reason == "missing"


def test_collect_docs_to_regenerate_flags_outdated_markdown(tmp_path: Path) -> None:
    source_root = tmp_path / "src"
    output_root = tmp_path / "docs"

    source_file = source_root / "pkg" / "Service.py"
    target_file = output_root / "pkg" / "Service.md"

    _write(source_file, "class Service: ...\n")
    _write(target_file, "# Service\n")

    target_file.touch()
    source_file.touch()

    stale = collect_docs_to_regenerate(source_root=source_root, output_root=output_root)

    assert len(stale) == 1
    assert stale[0].reason == "outdated"


def test_collect_docs_to_regenerate_ignores_up_to_date_markdown(tmp_path: Path) -> None:
    source_root = tmp_path / "src"
    output_root = tmp_path / "docs"

    source_file = source_root / "pkg" / "Service.py"
    target_file = output_root / "pkg" / "Service.md"

    _write(target_file, "# Service\n")
    _write(source_file, "class Service: ...\n")

    target_file.touch()

    stale = collect_docs_to_regenerate(source_root=source_root, output_root=output_root)
    assert stale == []


def test_collect_docs_to_regenerate_skips_tests_by_default(tmp_path: Path) -> None:
    source_root = tmp_path / "src"
    output_root = tmp_path / "docs"

    _write(source_root / "pkg" / "feature_test.py", "def test_x(): ...\n")

    stale = collect_docs_to_regenerate(source_root=source_root, output_root=output_root)
    assert stale == []


def test_collect_docs_to_regenerate_includes_tests_when_flag_enabled(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "src"
    output_root = tmp_path / "docs"

    test_file = source_root / "pkg" / "feature_test.py"
    _write(test_file, "def test_x(): ...\n")

    stale = collect_docs_to_regenerate(
        source_root=source_root,
        output_root=output_root,
        include_tests=True,
    )

    assert len(stale) == 1
    assert stale[0].source_file == test_file
    assert stale[0].target_file == output_root / "pkg" / "feature_test.md"


def test_target_markdown_path_preserves_relative_layout(tmp_path: Path) -> None:
    source_root = tmp_path / "src"
    output_root = tmp_path / "docs"
    source_file = source_root / "a" / "b" / "ClassName.py"

    assert target_markdown_path(source_file, source_root, output_root) == (
        output_root / "a" / "b" / "ClassName.md"
    )


def test_docs_sync_returns_non_zero_with_fail_on_stale(tmp_path: Path) -> None:
    source_root = tmp_path / "src"
    output_root = tmp_path / "docs"
    _write(source_root / "pkg" / "Service.py", "class Service: ...\n")

    runner = CliRunner()
    result = runner.invoke(
        docs,
        [
            "sync",
            "--source",
            str(source_root),
            "--output",
            str(output_root),
            "--fail-on-stale",
        ],
    )

    assert result.exit_code != 0
    assert "need regeneration" in result.output


def test_docs_sync_reports_up_to_date(tmp_path: Path) -> None:
    source_root = tmp_path / "src"
    output_root = tmp_path / "docs"

    source_file = source_root / "pkg" / "Service.py"
    target_file = output_root / "pkg" / "Service.md"

    _write(target_file, "# Service\n")
    _write(source_file, "class Service: ...\n")
    target_file.touch()

    runner = CliRunner()
    result = runner.invoke(
        docs,
        [
            "sync",
            "--source",
            str(source_root),
            "--output",
            str(output_root),
        ],
    )

    assert result.exit_code == 0
    assert "up to date" in result.output


def test_docs_sync_generate_requires_openai_api_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_root = tmp_path / "src"
    output_root = tmp_path / "docs"
    _write(source_root / "pkg" / "Service.py", "class Service: ...\n")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        docs,
        [
            "sync",
            "--source",
            str(source_root),
            "--output",
            str(output_root),
            "--generate",
        ],
    )

    assert result.exit_code != 0
    assert "OPENAI_API_KEY" in result.output


def test_generate_documentation_for_items_writes_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_file = tmp_path / "src" / "pkg" / "Service.py"
    target_file = tmp_path / "docs" / "pkg" / "Service.md"
    _write(source_file, "class Service: ...\n")

    class _FakeDocumentationAgent:
        def __init__(self, model: str) -> None:
            self.model = model

        def generate_and_write(self, source_file: Path, target_file: Path) -> str:
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_text(f"# Auto doc for {source_file.name}\n")
            return target_file.read_text()

    docs_module = importlib.import_module("naas_abi_cli.cli.docs")
    monkeypatch.setattr(docs_module, "DocumentationAgent", _FakeDocumentationAgent)

    generated_count = generate_documentation_for_items(
        stale_docs=[
            DocSyncItem(
                source_file=source_file,
                target_file=target_file,
                reason="missing",
            )
        ],
        model="gpt-5.2",
    )

    assert generated_count == 1
    assert target_file.exists()
    assert "Auto doc" in target_file.read_text()


def test_parse_dotenv_key_reads_values(tmp_path: Path) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        """
# comment
OPENAI_API_KEY="abc123"
export OTHER_KEY=value
""".strip()
        + "\n"
    )

    assert _parse_dotenv_key(dotenv_path, "OPENAI_API_KEY") == "abc123"
    assert _parse_dotenv_key(dotenv_path, "OTHER_KEY") == "value"
    assert _parse_dotenv_key(dotenv_path, "MISSING") is None


def test_resolve_openai_api_key_from_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("OPENAI_API_KEY=from_dotenv\n")

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    resolved = resolve_openai_api_key()

    assert resolved == "from_dotenv"


def test_docs_sync_generate_uses_dotenv_openai_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_root = tmp_path / "src"
    output_root = tmp_path / "docs"
    _write(source_root / "pkg" / "Service.py", "class Service: ...\n")
    _write(tmp_path / ".env", "OPENAI_API_KEY=from_dotenv\n")

    docs_module = importlib.import_module("naas_abi_cli.cli.docs")

    called: dict[str, int] = {"count": 0}

    called_workers: list[int] = []

    def _fake_generate(  # type: ignore[no-untyped-def]
        stale_docs,
        model: str,
        workers: int = 10,
    ) -> int:
        called["count"] += len(stale_docs)
        called_workers.append(workers)
        return len(stale_docs)

    monkeypatch.setattr(docs_module, "generate_documentation_for_items", _fake_generate)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    runner = CliRunner()
    result = runner.invoke(
        docs,
        [
            "sync",
            "--source",
            str(source_root),
            "--output",
            str(output_root),
            "--generate",
            "--workers",
            "10",
        ],
    )

    assert result.exit_code == 0
    assert called["count"] == 1
    assert called_workers == [10]
    assert "Generated 1 documentation file(s)." in result.output


def test_generate_documentation_for_items_rejects_invalid_workers() -> None:
    with pytest.raises(ValueError, match="workers must be >= 1"):
        generate_documentation_for_items(stale_docs=[], model="gpt-5.2", workers=0)
