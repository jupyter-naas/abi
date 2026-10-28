# {{module_name}} — AGENTS.md

A standalone repository for one remote ABI module. The module itself, its
rules and how to extend it: [`src/{{module_name_snake}}/AGENTS.md`](src/{{module_name_snake}}/AGENTS.md).

- Python package: `src/{{module_name_snake}}/`, built with hatchling.
- Dependencies: `naas-abi-sdk[agent,otel,workflows,rdf]` and `naas-abi-proto` only, from the
  ABI repository at `{{abi_git_ref}}`. **Never add `naas-abi-core`**, `naas-abi`
  or `naas-abi-marketplace`: the Dockerfile and the tests reject it.
- Commands: `uv sync`, `uv run pytest`, `uvx ruff check src`,
  `docker build -t {{module_name}} .`.
- SDK reference: <https://github.com/jupyter-naas/abi/blob/{{abi_git_ref}}/libs/naas-abi-sdk/README.md>.
