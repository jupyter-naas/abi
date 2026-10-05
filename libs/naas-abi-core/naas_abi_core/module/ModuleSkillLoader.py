"""Discover skill package entry points without executing package code."""

from pathlib import Path


class ModuleSkillLoader:
    @staticmethod
    def load_skills(module_root: str) -> list[str]:
        root = Path(module_root) / "skills"
        return [
            str(path)
            for path in sorted(root.glob("*/SKILL.md"))
            if path.is_file()
            and not path.parent.name.startswith(".")
            and path.resolve().is_relative_to(root.resolve())
        ]
