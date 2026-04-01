import os
import sys

# Ensure repo root is on sys.path for root-level test discovery
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# These files use relative imports or depend on package-scoped sys.path
# manipulation that breaks when pytest collects them from the monorepo root.
# They are exercised correctly when running pytest from within their package
# directory (e.g. `uv run pytest libs/naas-abi-core`).
collect_ignore = [
    # These use relative imports that only work when pytest is run from within
    # the package directory (e.g. `uv run pytest libs/naas-abi-core`).
    "libs/naas-abi-core/naas_abi_core/services/bus/tests/bus__secondary_adapter__generic_test.py",
    "libs/naas-abi-core/naas_abi_core/services/keyvalue/tests/kv__secondary_adapter__generic_test.py",
    "libs/naas-abi-core/naas_abi_core/services/vector_store/adapters/QdrantAdapter_test.py",
    # These require the `testcontainers` package which is only available in the
    # naas-abi-core dev environment. Run via `make test-integration-core`.
    "libs/naas-abi-core/naas_abi_core/services/triple_store/adaptors/secondary/ApacheJenaTDB2_integration_test.py",
    "libs/naas-abi-core/naas_abi_core/services/triple_store/adaptors/secondary/Oxigraph_integration_test.py",
]
