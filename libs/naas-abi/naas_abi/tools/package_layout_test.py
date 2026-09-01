from pathlib import Path

import naas_abi.skills
import naas_abi.tools


def test_tools_and_skills_are_package_capabilities() -> None:
    abi_root = Path(naas_abi.tools.__file__).resolve().parents[1]
    assert (abi_root / "tools" / "web_tools.py").is_file()
    assert (abi_root / "tools" / "slides_tools.py").is_file()
    assert (abi_root / "skills" / "slides" / "SKILL.md").is_file()
    assert (abi_root / "skills" / "slides_policy.py").is_file()
    assert not (abi_root / "agents" / "tools").exists()
    assert not (abi_root / "agents" / "skills").exists()
    assert not (abi_root / "agents" / "slides_policy.py").exists()
    assert naas_abi.skills.__file__ is not None
    assert "agents" not in Path(naas_abi.skills.__file__).parts[-3:]


def test_web_search_lives_in_abi_tools() -> None:
    from naas_abi.tools.web_tools import make_web_search_tool

    assert make_web_search_tool().name == "web_search"
