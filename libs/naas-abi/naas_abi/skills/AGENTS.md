# naas_abi.skills

Package skills that any `naas_abi` agent can import. Not children of an agent class.

Layout: `skills/<name>/SKILL.md` with YAML frontmatter (same as Cursor and zen).

| Path | What it is |
|---|---|
| `slides/SKILL.md` | Nexus Slides office skill. |
| `slides_policy.py` | Shared slides research/write policy (next to the skill). |
| `office_skills.py` | Loader + `list_office_skills` / `read_office_skill` tools. |

`SlidesAgent` imports the slides skill and policy. It does not own the files. Do not register DocsAgent or SheetsAgent here until those products exist.

Zen keeps a tenant pointer at `src/zen/skills/slides/SKILL.md`.
