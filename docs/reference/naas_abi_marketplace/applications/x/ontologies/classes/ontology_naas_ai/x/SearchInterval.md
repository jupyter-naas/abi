# SearchInterval

## What it is
- A thin wrapper class around `XSearchRecentTweetsProcess.SearchInterval`.
- Intended as an action class hook point where custom logic can be added by overriding `actions()`.

## Public API
- `class SearchInterval(_SearchInterval)`
  - Inherits all behavior from `_SearchInterval` (imported alias).
  - `actions(self)`
    - Placeholder action method meant to be implemented with custom logic.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_marketplace.applications.x.ontologies.processes.XSearchRecentTweetsProcess.SearchInterval` (imported as `_SearchInterval`).

## Usage
```python
from naas_abi_marketplace.applications.x.ontologies.classes.ontology_demo.x.SearchInterval import SearchInterval

class MySearchInterval(SearchInterval):
    def actions(self):
        # implement your logic here
        pass
```

## Caveats
- `actions()` is empty in this module; it does not execute any logic unless implemented.
- The inherited behavior and expected interface come from `_SearchInterval` (not shown here).
