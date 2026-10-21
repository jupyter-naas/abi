# `search_users.users` (Users dataset publisher)

## What it is
Publishes an object-storage-backed dataset used by the X app “Users” search page. It writes:
- `search_users/users.json`: compact search index of all authors
- `search_users/shards.json`: shard manifest (hashes, counts, fingerprints)
- `search_users/posts/<shard>.json`: per-shard payload containing profiles and full post lists

Sharding is based on `sha1(username)` via `user_shard()`, enabling the web app to fetch only one small shard file per selected user.

## Public API
- `publish(ctx: SnapshotContext, *, full: bool = False) -> dict`
  - Builds and writes the index and shard files.
  - Incremental by default:
    - Uses per-shard `fingerprint` (derived from `all_authors()` aggregate data) to decide which shards are stale.
    - For stale shards only, queries accounts and posts and conditionally uploads the shard payload if bytes changed.
  - If `full=True`, forces rebuilding all shards (also happens when previous manifest is missing/incompatible).
  - Returns a summary dict:
    - `users`, `posts`, `shards_rebuilt`, `shards_written`, `shards_unchanged`

## Configuration/Dependencies
Imports from `naas_abi_marketplace.applications.x.apps.x.api.common`:
- `SnapshotContext` (provides data access and storage I/O)
- `USER_SHARD_COUNT`, `USER_SHARD_HEX` (shard layout metadata)
- `user_shard(username)` (shard key function)
- `encode_compact(obj) -> bytes` (compact serialization used for payload/hash)
- `content_digest(bytes) -> str` (digest used for content hashing)

Other notable constants in this module:
- `DATASET_FORMAT = 1` (written into index/shards and shard payload)
- `INDEX_COLUMNS` (column order for compact index rows)
- `MAX_DESCRIPTION_CHARS = 160` (bio truncation bound for index)

`SnapshotContext` is expected to provide (used here):
- `built_at` (datetime)
- `all_authors() -> list[dict]`
- `all_descriptions() -> dict[str, str]`
- `accounts_for_usernames(usernames: list[str]) -> dict[str, dict]`
- `posts_for_usernames(usernames: list[str]) -> dict[str, list]`
- `save_json_compact(prefix, name, doc)`, `read_json(prefix, name)`
- `save_bytes(prefix, name, data: bytes)`

## Usage
```python
from naas_abi_marketplace.applications.x.apps.x.api.search_users.users import publish

# ctx must be a SnapshotContext instance with storage + query backends configured
summary = publish(ctx)          # incremental publish
# summary = publish(ctx, full=True)  # force full rebuild

print(summary)
```

## Caveats
- Incremental staleness is driven by tweet-derived author state (`username`, `posts`, `last_post_at`, `location`, `verified_type`). Profile/account changes that arrive without a new post may not be published until the shard is rebuilt (or `full=True` is used).
- Index rows are arrays (not objects) and must be interpreted using `INDEX_COLUMNS`.
