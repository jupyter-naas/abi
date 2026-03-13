# Documentation Maintenance Skill (naas-abi-core)

Use this guide when creating or updating documentation in `libs/naas-abi-core/docs`.

## Objective

Keep user documentation accurate, navigable, and tightly aligned with runtime code behavior.

## Source of Truth

1. Runtime code in `naas_abi_core/`.
2. `pyproject.toml` for dependencies/extras/scripts.
3. Existing docs in this directory for style/navigation.

Do not document assumptions as facts. If behavior is uncertain, mark it explicitly.

## Required Documentation Rules

1. Use Markdown only.
2. Use Quartz/Obsidian wiki links (`[[Page-Name]]`) for internal cross-links.
3. Prefer one topic per page.
4. Keep examples minimal but runnable.
5. Use implementation-accurate names (`EngineConfiguration`, `TripleStoreService`, etc.).
6. Never claim support for a backend/feature unless implemented in current code.

## Naming and Structure

- Use short, explicit page names with hyphens for concepts.
- Group by folders when appropriate:
  - `services/`
  - `apps/`
  - `modules/`
- Ensure `docs/index.md` links every newly created page.

## Update Workflow

When code changes impact docs, follow this sequence:

1. Identify impacted pages.
2. Update behavior, config snippets, and examples.
3. Add/remove links in `docs/index.md`.
4. Add at least one “Related pages” line in updated pages.
5. Verify terminology consistency across pages.

## Content Checklist (per changed page)

- What it is.
- Why/when to use it.
- How to configure/run it.
- Key caveats and limits.
- Links to adjacent topics.

## Accuracy Checklist

- Config keys exactly match pydantic configuration models.
- Endpoint paths/methods match actual app routers.
- Service adapter lists match available adapter classes.
- Environment variable names match code usage.

## Link Quality Checklist

- No orphan pages (every page linked from at least one other page).
- No dead links in `[[...]]` format.
- Prefer relative conceptual links over repeating content.

## Style Guidelines

- Keep a practical, operator-focused tone.
- Prefer bullets over long paragraphs.
- Use fenced code blocks with language tags.
- Avoid marketing language; prioritize operational clarity.

## Anti-Patterns to Avoid

- Copying stale README content without code verification.
- Documenting deprecated/removed behavior as active.
- Adding large narrative sections with no runnable examples.
- Duplicating the same instructions across many pages instead of linking.

## Definition of Done

Documentation update is complete when:

1. All impacted pages are updated.
2. New pages are indexed in `docs/index.md`.
3. Internal wiki links are present and valid.
4. Examples and claims match current code.
