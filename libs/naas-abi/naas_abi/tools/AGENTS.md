# naas_abi.tools

Package capabilities that any `naas_abi` agent can import. Not children of an agent class.

| Module | What it is |
|---|---|
| `web_tools` | `web_search` + `web_fetch` (ddgs). Shared search stack. |
| `slides_tools` | Nexus Slides deck read/write. |
| `nexus_admin_tools` | Org/workspace admin for AbiAgent. |
| `platform_tools` | Knowledge graph and platform data services. |

Agents import these (`from naas_abi.tools.web_tools import make_web_search_tool`). Do not put tool modules under `naas_abi.agents`.

Tests sit next to the source (`*_test.py`).
