# SPARQLTerminal

## What it is
A simple interactive terminal loop for running SPARQL queries against a triple store service, with basic commands (`exit`, `help`, `clear`) and formatted output via `terminal_style` helpers.

## Public API
- `class SPARQLTerminal`
  - `__init__(triple_store_service: ITripleStoreService)`
    - Stores a triple store service used to execute SPARQL queries.
  - `execute_query(query)`
    - Calls `triple_store_service.query(query)` and returns results.
    - Wraps any exception as `Exception("Error executing query: ...")`.
  - `run()`
    - Starts the interactive terminal:
      - Reads user input via `get_user_input()`
      - Handles commands:
        - `exit`: prints “Goodbye!” and returns
        - `help`: reprints welcome message
        - `clear`: clears the screen
        - empty/whitespace: ignored
      - Otherwise prints the query, executes it, prints results, prints dividers, and prints errors on failure.

- `main()`
  - Obtains `triple_store_service` from `ABIModule.get_instance().engine.services.triple_store`.
  - Creates `SPARQLTerminal` and runs it.

## Configuration/Dependencies
- Depends on UI/formatting functions from `naas_abi.apps.sparql_terminal.terminal_style`:
  - `clear_screen`, `get_user_input`, `print_divider`, `print_query`, `print_query_error`, `print_query_result`, `print_system_message`, `print_welcome_message`
- Requires a triple store service implementing `naas_abi_core.services.triple_store.TripleStorePorts.ITripleStoreService` with a `query(query: str)` method.
- `main()` depends on `naas_abi.ABIModule` being available and configured with `engine.services.triple_store`.

## Usage
### Run as a script (uses `ABIModule` wiring)
```python
from naas_abi.apps.sparql_terminal.main import main

main()
```

### Embed with your own triple store service
```python
from naas_abi.apps.sparql_terminal.main import SPARQLTerminal

# triple_store_service must provide: query(str) -> results
terminal = SPARQLTerminal(triple_store_service)
terminal.run()
```

## Caveats
- `execute_query()` catches all exceptions and re-raises a generic `Exception` with a prefixed message (original exception type is not preserved).
- The interactive loop runs indefinitely until the user enters `exit`.
