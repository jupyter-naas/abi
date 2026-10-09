"""The ``.manifest.json`` written at the root of a drive."""

MANIFEST_NAME = ".manifest.json"
# The first version wrote it without the leading dot; backfill removes those.
LEGACY_MANIFEST_NAME = "manifest.json"
SCHEMA_VERSION = 1
