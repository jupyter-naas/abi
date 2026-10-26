# integrations — AGENTS.md

Integrations of this remote module: how it reaches a third-party tool. Written
like in-engine ones, on `naas_abi_sdk` only (`from naas_abi_sdk.integration
import Integration, ...`; never `naas_abi_core`). Create one with
`abi new integration <Name> integrations` from the module folder.

- An `Integration` takes an `IntegrationConfiguration` (a dataclass with the
  credentials and settings). Raise `IntegrationConnectionError` when the tool
  cannot be reached. Standard library only: bring your own async HTTP client.
- The module does not discover or serve integrations: its workflows, pipelines
  and agents build and call them.
- Credentials come from `await self.engine.services.secret.get("KEY")` (declare
  `secret` in `ModuleDependencies`), never from the environment. A workflow
  or pipeline that needs one defines a `New(module)` that reads it.
- Tests sit beside the code, `<Name>Integration_test.py`, and run offline.
