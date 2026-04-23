# `naas_abi_core.utils.onto2py.__main__`

## What it is
- The module entry point that enables running `onto2py` via `python -m onto2py`.
- Reads a TTL file path from the command line, converts it to Python code using `onto2py()`, and writes the result to an output file.

## Public API
- `main()`
  - CLI handler for module execution.
  - Validates arguments, calls `onto2py(ttl_file)`, writes output, and returns via `sys.exit()` on error.

## Configuration/Dependencies
- Standard library:
  - `sys` (for CLI arguments and exit codes)
- Internal dependency:
  - `from .onto2py import onto2py` (must exist and accept a TTL file path, returning Python code as a string)

## Usage
Run as a module from the command line:

```bash
python -m onto2py path/to/input.ttl path/to/output.py
```

Programmatic usage (minimal example):

```python
from naas_abi_core.utils.onto2py.__main__ import main

# Expects sys.argv to be set by the interpreter (typical CLI execution).
main()
```

## Caveats
- Requires at least 2 CLI arguments: `<ttl_file> <output_file>`; otherwise exits with status code `1`.
- Any exception raised by `onto2py()` or file I/O is caught, printed, and causes exit with status code `1`.
- Prints status messages to stdout, including checkmark/cross symbols.
