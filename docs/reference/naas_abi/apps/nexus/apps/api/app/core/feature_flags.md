# feature_flags

## What it is
- Utility module for computing **effective boolean feature flags** for a user in a workspace.
- Produces a dict for a fixed set of known feature keys:
  - `chat`, `files`, `agents`, `knowledge`, `settings`

## Public API
- `KNOWN_FEATURE_KEYS: tuple[str, ...]`
  - Canonical list of supported feature flag keys.
- `build_feature_flags(*, role: str, feature_flags_config: FeatureFlagsConfig, workspace_slug: str | None, workspace_id: str | None) -> dict[str, bool]`
  - Builds the effective feature flag map by combining:
    - role baseline defaults
    - workspace-level overrides
    - enabled feature catalog filtering

## Configuration/Dependencies
- Depends on `FeatureFlagsConfig` from `naas_abi.apps.nexus.apps.api.app.core.config`.
- Expected fields used on `feature_flags_config`:
  - `enabled_features: list[str]`
  - `role_baseline: Mapping[str, list[str]]` (role → list of enabled keys)
  - `workspace_overrides: Mapping[str, Mapping[str, bool]]` (workspace slug or id → key → bool)

Resolution rules:
- **Enabled catalog**:
  - If `enabled_features` contains any known keys, only those known keys are considered enabled.
  - If it contains no known keys (or is empty), all `KNOWN_FEATURE_KEYS` are treated as enabled.
- **Workspace override selection**:
  - Prefer `workspace_slug` match in `workspace_overrides`
  - Else try `workspace_id` match
  - Else no overrides

## Usage
```python
from naas_abi.apps.nexus.apps.api.app.core.feature_flags import build_feature_flags

# FeatureFlagsConfig is imported from your app's config module
from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig

cfg = FeatureFlagsConfig(
    enabled_features=["chat", "files"],  # only these are eligible to be enabled
    role_baseline={"admin": ["chat", "agents"], "user": ["chat"]},
    workspace_overrides={
        "acme": {"files": True, "agents": True},  # "agents" will be ignored (not enabled in catalog)
    },
)

flags = build_feature_flags(
    role="admin",
    feature_flags_config=cfg,
    workspace_slug="acme",
    workspace_id=None,
)

print(flags)
# Example output:
# {'chat': True, 'files': True, 'agents': False, 'knowledge': False, 'settings': False}
```

## Caveats
- Only keys in `KNOWN_FEATURE_KEYS` are returned; unknown keys in config are ignored.
- Workspace overrides only apply if the feature key is in the enabled catalog.
- If `enabled_features` contains **no known keys**, the module treats **all known features as enabled** (catalog defaults to `KNOWN_FEATURE_KEYS`).
