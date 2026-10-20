# IAMService

## What it is
A small IAM (Identity and Access Management) helper that checks whether an authenticated user token grants a required scope, with simple wildcard (`*`) matching, and raises a dedicated permission error when access is denied.

## Public API
- `IAMPermissionError(scope: str)`
  - Raised when a required scope is missing.
  - `__str__()` returns `"missing_scope:<scope>"`.

- `IAMService(policy: object | None = None)`
  - Constructs the service; `policy` is stored but not used in this module.

- `IAMService.is_allowed(token_data: TokenData, required_scope: str) -> bool`
  - Returns `True` if:
    - `token_data.is_authenticated` is truthy
    - `token_data.user_id` is present
    - `token_data.scopes` is non-empty
    - at least one granted scope matches `required_scope` (supports `*` wildcard)

- `IAMService.ensure(token_data: TokenData, required_scope: str) -> None`
  - Calls `is_allowed`; raises `IAMPermissionError(scope=required_scope)` if not allowed.

## Configuration/Dependencies
- Depends on `TokenData` from `naas_abi.apps.nexus.apps.api.app.services.iam.port`.
  - Expected fields used here:
    - `is_authenticated`
    - `user_id`
    - `scopes` (iterable of strings)

- Uses Python `re`:
  - Matching is performed with `re.fullmatch` against the *required* scope.
  - Granted scopes may contain `*` which expands to `.*` (regex wildcard).

## Usage
```python
from naas_abi.apps.nexus.apps.api.app.services.iam.service import IAMService, IAMPermissionError
from naas_abi.apps.nexus.apps.api.app.services.iam.port import TokenData

iam = IAMService()

token = TokenData(is_authenticated=True, user_id="u1", scopes=["nexus:*", "read:reports"])

if iam.is_allowed(token, "nexus:projects:read"):
    print("allowed")

try:
    iam.ensure(token, "admin:delete")
except IAMPermissionError as e:
    print(str(e))  # missing_scope:admin:delete
```

## Caveats
- Scope checks are denied if:
  - `is_authenticated` is falsey, or `user_id` is missing/falsey, or `scopes` is empty/falsey.
- Wildcard matching only applies to `*` in the granted scope pattern; matching is full-string (`fullmatch`), not substring.
- The `policy` argument is currently unused in this implementation.
