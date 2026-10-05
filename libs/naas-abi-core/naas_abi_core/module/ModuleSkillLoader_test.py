from naas_abi_core.module.ModuleSkillLoader import ModuleSkillLoader


def test_discovers_only_skill_entry_points_inside_module(tmp_path):
    for path in (
        "skills/report/SKILL.md",
        "skills/report/references/note.md",
        "skills/.hidden/SKILL.md",
        "agents/skills/other/SKILL.md",
    ):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("content")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "SKILL.md").write_text("content")
    (tmp_path / "skills/escape").symlink_to(outside, target_is_directory=True)
    assert ModuleSkillLoader.load_skills(str(tmp_path)) == [
        str(tmp_path / "skills/report/SKILL.md")
    ]
    assert ModuleSkillLoader.load_skills(str(tmp_path / "missing")) == []
