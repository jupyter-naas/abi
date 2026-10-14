---
name: Skill creator
description: Register one workspace skill with a name, a description, and a prompt body.
when_to_use: The user asks to create a skill or register a workspace skill.
---

# Skill creator

Run this when the user asks to create a skill.

Call create_skill to register the workspace skill. Pass the name, the description, and the prompt body. The tool writes the Postgres skill row that Settings lists. Do not write a file yourself.

If the user supplied extra files, store them with the existing package writer write_skill_package. It stores them under ~/.naas/skills/<workspace id>/<slug>/. Do not invent a new writer.

Do not run an evaluation loop. Do not publish a marketplace entry. Do not claim the skill was packaged or tested.
