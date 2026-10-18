---
sidebar_position: 3
---

# Publishing to the Marketplace

To publish a module to the Marketplace, you contribute it to the ABI repository (`jupyter-naas/abi`) with a pull request. There is no separate publishing step.

1. **Build and test the module in your project.** Create it with `abi new module <name> --in-engine`, and make it work from `src/<name>/` first.

2. **Pick its place in the package.** Under `libs/naas-abi-marketplace/naas_abi_marketplace/`:
   - `ai/<provider>/` for a model provider;
   - `applications/<app>/` for a third-party integration;
   - `domains/<bucket>/...` for a domain capability. The repository's `domains/AGENT.md` explains how to choose the bucket and the component folder.

3. **Match the conventions of the category.** Copy a neighbouring module: an `ABIModule` in `__init__.py` with its `dependencies` and a typed `Configuration` (with a docstring showing the `config.yaml` entry), `PascalCase.py` files, and agents written like the neighbouring ones. The marketplace's `AGENTS.md` (`libs/naas-abi-marketplace/AGENTS.md`) describes the module shape and has a checklist for a new module.

4. **Add the tests and the README.**
   - `<Name>Agent_test.py` next to each agent, that exercises it.
   - `on_load_test.py` that checks the module loads with a minimal configuration.
   - A README with setup, configuration and examples.

5. **Declare its dependencies.** If the module needs third-party libraries, add an extra named `<category>-<module>` to `libs/naas-abi-marketplace/pyproject.toml`.

6. **Open a pull request on ABI and ask for review.** Run the module's tests first:

   ```bash
   uv run pytest libs/naas-abi-marketplace/naas_abi_marketplace/applications/my_app
   ```

## Publishing Guidelines

- **Self-contained**: minimize dependencies on other modules.
- **Well-documented**: a README with setup and usage instructions.
- **Tested**: unit tests; mock the external service, and keep tests that need real credentials separate so they can be skipped.
- **Licensed**: state the license of your contribution.

## Sharing a module without the Marketplace

A module that stays private, or that a team ships on its own schedule, does not need the Marketplace. Keep it in your project's `src/`, or create a [remote module](/user-guide/build/sdk/build-a-remote-module) in a repository of its own with `abi new module <name> --standalone`.
