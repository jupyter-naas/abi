# SPARQLTerminal

## What it is
- An interactive terminal loop for executing SPARQL queries against a triple store service.
- Provides basic commands (`help`, `clear`, `exit`) and prints query results/errors using a shared terminal styling module.

## Public API
- `class SPARQLTerminal(triple_store_service: ITripleStoreService)`
  - Wraps a triple store service and exposes an interactive CLI.
  - Methods:
    - `execute_query(query)`
      - Executes `triple_store_service.query(query)` and returns results.
      - Raises `Exception("Error executing query: ...")` on failure.
    - `run()`
      - Starts the terminal UI loop:
        - `exit`: prints goodbye and returns
        - `help`: reprints welcome message
        - `clear`: clears the screen
        - empty input: ignored
        - otherwise: prints the query, executes it, prints results or error
- `main()`
  - Loads the triple store service from `naas_abi.ABIModule`, constructs `SPARQLTerminal`, and runs it.

## Configuration/Dependencies
- Requires an implementation of `naas_abi_core.services.triple_store.TripleStorePorts.ITripleStoreService` with a `.query(query: str)` method.
- Uses terminal helpers from `naas_abi.apps.sparql_terminal.terminal_style`:
  - `clear_screen`, `get_user_input`, `print_divider`, `print_query`, `print_query_error`, `print_query_result`, `print_system_message`, `print_welcome_message`.
- `main()` depends on `naas_abi.ABIModule` and its singleton engine wiring:
  - `ABIModule.get_instance().engine.services.triple_store`

## Usage
### Run as a script (uses `ABIModule` wiring)
```bash
python -m naas_abi.apps.sparql_terminal.main
```

### Use programmatically with a triple store service
```python
from naas_abi.apps.sparql_terminal.main import SPARQLTerminal

# triple_store_service must implement .query(str) -> results
terminal = SPARQLTerminal(triple_store_service)
terminal.run()
```

## Caveats
- `execute_query` wraps all exceptions into a generic `Exception`, which can obscure original exception types.
- The terminal loop runs indefinitely until the user types `exit`.
