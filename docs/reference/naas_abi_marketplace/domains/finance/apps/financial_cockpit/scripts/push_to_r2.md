# push_to_r2.py

## What it is
- Standalone CLI script to mirror the local demo datastore (`web/data`) into a Cloudflare R2 bucket under a configurable key prefix (default: `data`).
- Designed to match the key layout expected by the app when running in production mode.
- Includes safety controls:
  - `--dry-run` to print intended actions without writing.
  - Skips upload when remote ETag (MD5) matches local MD5.
  - Never uploads files under runtime-owned prefixes to avoid overwriting live user state.

## Public API
- `main() -> int`
  - CLI entrypoint. Scans local datastore, prints plan, and (optionally) uploads to R2.
- `is_runtime_owned(rel_key: str) -> bool`
  - Returns `True` when a relative key is within protected runtime-owned prefixes.
- `md5_hex(data: bytes) -> str`
  - Computes MD5 hex digest for byte content (used to compare with remote ETag).
- `make_client(account_id: str, access_key: str, secret_key: str)`
  - Builds a boto3 S3 client configured for Cloudflare R2.
- `remote_etag(client, bucket: str, key: str) -> str | None`
  - Fetches an object’s ETag via `head_object`; returns `None` on error.
- `iter_local_files(root: Path)`
  - Yields `(path, relative_posix_key)` for all files under `root`, sorted.

## Configuration/Dependencies
- Dependency: `boto3` (and `botocore` via boto3). The script exits if not installed.
- Local input directory:
  - `LOCAL_DATA_DIR = <repo>/.../web/data` (resolved relative to this script).
- Environment variables (also available as CLI flags):
  - `R2_ACCOUNT_ID` (`--account-id`)
  - `R2_ACCESS_KEY_ID` (`--access-key-id`)
  - `R2_SECRET_ACCESS_KEY` (`--secret-access-key`)
  - `R2_BUCKET` (`--bucket`, default `app-financial-cockpit`)
  - `R2_DATA_PREFIX` (`--prefix`, default `data`)
- Protected (runtime-owned) relative key prefixes (never uploaded):
  - `globals/users.json`
  - `globals/pnl/`
  - `user_annotations/`

## Usage
Dry-run (no credentials required):
```bash
python scripts/push_to_r2.py --dry-run
```

Live push (credentials via env):
```bash
export R2_ACCOUNT_ID=...
export R2_ACCESS_KEY_ID=...
export R2_SECRET_ACCESS_KEY=...
export R2_BUCKET=app-financial-cockpit

python scripts/push_to_r2.py
```

Change target key prefix:
```bash
python scripts/push_to_r2.py --prefix data
```

## Caveats
- Requires `web/data` to exist relative to the script; otherwise it returns an error string.
- ETag comparison assumes the remote ETag equals the MD5 of the uploaded bytes; if the backend changes ETag semantics, change-detection may be unreliable.
- Runtime-owned prefixes are always skipped (cannot be seeded by this script).
