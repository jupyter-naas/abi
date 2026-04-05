# Secret Service

`Secret` is a multi-adapter facade for reading/writing secrets.

## Behavior

- `get(key)` checks adapters in order and returns first match.
- `set(key, value)` writes to all adapters.
- `remove(key)` removes from all adapters.
- `list()` merges all adapter values (earlier adapters have higher priority).

## Adapter options

- `dotenv`: reads and writes `.env` file (path configurable).
- `naas`: uses Naas secret HTTP API.
- `base64`: stores a base64-encoded dotenv payload inside another secret adapter.
- `custom`: pluggable adapter.

## Important notes

- Dotenv adapter fails at startup if configured file does not exist.
- During config rendering, missing secrets may be prompted interactively if TTY is available.
- In non-interactive runtime, missing required secret raises a clear error.

## Example

```yaml
services:
  secret:
    secret_adapters:
      - adapter: "dotenv"
        config:
          path: ".env"
```
