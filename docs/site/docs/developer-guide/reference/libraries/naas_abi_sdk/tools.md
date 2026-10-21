# tools

## What it is
- The declarations and the client side of a tool a module serves over NATS (`abi.tool.v1`).
- Stdlib and protobuf only: importable without the host's optional `jsonschema`.
- A module declares `ToolDescriptor`s, binds a handler to each with `BaseModule.expose_tool`, and `ToolHost` ([tool_host](tool_host.md)) serves them. Discovery stores the descriptors as the portable `abi.tool_registry.v1.ToolDefinition`; the engine publishes them to its tool registry while the module has a ready instance. See `docs/adr/20261022_remote-module-tools.md`.

## Public API
- `ToolDescriptor(name, description, input_schema={"type": "object", "properties": {}}, version="1", output_schema=None, tags=(), config=(), required_scopes=())`
  - `name`: `[A-Za-z0-9_-]{1,64}`; one version per name. `input_schema`: a JSON Schema object every call's arguments are validated against, before the handler runs.
  - `to_pb(module_id)` / `from_pb(definition)`: the definition discovery stores (canonical JSON, so replicas of a module compare equal).
- `ToolConfig(key, description="", required=True)`: a **non-secret** configuration value the tool takes from the record that binds it. Engine secrets never reach a module: discovery refuses a secret requirement, and the composer rejects a `{secret: NAME}` binding on a remote tool. The module holds its own credentials.
- `ToolError`: raise it from a handler to report a failure the caller may read. Any other exception is logged in the module and reported as a generic `Tool execution failed`.
- `ToolCaller(identity, admin=False, user_id=None, workspace_id=None)` with `.engine` (the identity is one of the engine's own processes); `ToolCall(tool, caller, config, trace_id)`.
- `tool_subject(project, instance_id, name)`: `abi.mod.<project>.<instance>.tool.<name>.invoke`.
- `ModuleToolClient(transport, subject, instance_id).invoke(request, *, timeout=None)`: the unary call (`timeout`: the wait and the handler's deadline); `ModuleProxy.call_tool(name, arguments, *, config=None)` wraps it.
- Limits: request 512 KiB, arguments 256 KiB, configuration 64 KiB, result 512 KiB, deadline at most 300 s.

## Usage
```python
class ABIModule(BaseModule):
    module_id = "acme_crm"
    tools = (
        ToolDescriptor(
            "open_ticket",
            "Create a new ticket to report a bug or defect.",
            {
                "type": "object",
                "properties": {"title": {"type": "string"}},
                "required": ["title"],
            },
            config=(ToolConfig("region"),),
        ),
    )

    def on_initialized(self):
        self.expose_tool("open_ticket", self.open_ticket)

    async def open_ticket(self, arguments, call):  # ``call`` is optional
        return {"ticket": await crm(self.configuration).create(arguments["title"], call.config["region"])}

    def authorize_tool(self, name, caller):
        # Default: the engine's own processes only. This replaces it.
        return caller.engine or caller.identity == "billing_module"
```
