# Skill package

Register a workspace skill when the user asks to create one. Call `create_skill` with the name, the description, and the prompt body. Do not write a file yourself.

`create_skill` writes the Postgres skill row that Settings lists.

If the user supplied extra files, store them with the existing package writer `write_skill_package`. It stores them under `~/.naas/skills/<workspace id>/<slug>/`. Do not invent a new writer.

A stored package still has three single-line fields: `name`, `description`, and `when_to_use`. The chat catalog receives those three fields and does not receive the prompt body.

Do not run an evaluation loop, publish a marketplace entry, or claim the skill was packaged.
