# `naas_abi_core.utils.onto2py.__main__`

## What it is
- The module entry point for running `onto2py` via `python -m ...`.
- Converts a Turtle (`.ttl`) file into generated Python code and writes it to an output file.

## Public API
- `main()`
  - CLI-style function that:
    - Reads `<ttl_file>` and `<output_file>` from `sys.argv`.
    - Calls `onto2py(ttl_file)` to generate Python source code.
    - Writes the generated code to `<output_file>`.
    - Exits with status `1` on incorrect usage or conversion/write errors.

## Configuration/Dependencies
- Standard library:
  - `sys` for CLI argument handling and exit codes.
- Internal dependency:
  - `from .onto2py import onto2py` (must be available and callable as `onto2py(ttl_file)`).

## Usage
Run as a module (expects two arguments: input TTL file and output Python file):

```bash
python -m naas_abi_core.utils.onto2py input.ttl output.py
```

Programmatic invocation (uses `sys.argv`):

```python
from naas_abi_core.utils.onto2py.__main__ import main

# Ensure sys.argv is set appropriately before calling main()
main()
```

## Caveats
- Requires at least two CLI arguments; otherwise prints usage and exits with code `1`.
- Any exception during conversion or file writing is caught, printed, and causes exit code `1`.
- The success/error messages include Unicode symbols (✅ / ❌).
