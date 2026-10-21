"""Agent records as files: ``<directory>/<name>.yaml`` (or ``.yml`` / ``.json``).

The simplest durable store, and the one a repository or a deployment can
version alongside its configuration. New records are written as YAML.
"""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Any

import yaml
from naas_abi_core.services.agent_composer.AgentComposerPort import (
    AGENT_NAME_PATTERN,
    AgentSpec,
    AgentSpecInvalidError,
    AgentSpecNotFoundError,
    IAgentSpecRepository,
)
from pydantic import ValidationError

_EXTENSIONS = (".yaml", ".yml", ".json")


class FileSystemAgentSpecRepositoryAdapter(IAgentSpecRepository):
    def __init__(self, directory: str | Path) -> None:
        self._directory = Path(directory)
        self._lock = threading.Lock()

    def _files(self, name: str) -> list[Path]:
        if not re.match(AGENT_NAME_PATTERN, name):
            raise AgentSpecNotFoundError(name)
        return [
            path
            for path in (self._directory / f"{name}{ext}" for ext in _EXTENSIONS)
            if path.is_file()
        ]

    @staticmethod
    def _read(path: Path) -> AgentSpec:
        try:
            text = path.read_text(encoding="utf-8")
            data: Any = (
                json.loads(text) if path.suffix == ".json" else yaml.safe_load(text)
            )
            spec = AgentSpec.model_validate(data)
        except (OSError, ValueError, yaml.YAMLError, ValidationError) as exc:
            raise AgentSpecInvalidError(path.stem, [f"{path}: {exc}"]) from exc
        if spec.name != path.stem:
            raise AgentSpecInvalidError(
                path.stem,
                [
                    f"{path} declares name '{spec.name}'; the file must be named after it"
                ],
            )
        return spec

    def get(self, name: str) -> AgentSpec:
        files = self._files(name)
        if not files:
            raise AgentSpecNotFoundError(name)
        if len(files) > 1:
            raise AgentSpecInvalidError(
                name,
                [f"more than one file holds this record: {', '.join(map(str, files))}"],
            )
        return self._read(files[0])

    def list(self) -> list[AgentSpec]:
        if not self._directory.is_dir():
            return []
        names = sorted(
            {p.stem for p in self._directory.iterdir() if p.suffix in _EXTENSIONS}
        )
        return [self.get(name) for name in names]

    def save(self, spec: AgentSpec) -> None:
        with self._lock:
            self._directory.mkdir(parents=True, exist_ok=True)
            for existing in self._files(spec.name):
                existing.unlink()
            payload = spec.model_dump(mode="json", exclude_defaults=False)
            (self._directory / f"{spec.name}.yaml").write_text(
                yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )

    def delete(self, name: str) -> None:
        with self._lock:
            files = self._files(name)
            if not files:
                raise AgentSpecNotFoundError(name)
            for path in files:
                path.unlink()
