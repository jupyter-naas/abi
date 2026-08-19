#!/usr/bin/env python3
"""Seed a Cloudflare R2 bucket from the app's local demo datastore.

Standalone (only needs boto3) so the template carries no ABI runtime
dependency. It mirrors the local ``web/data`` tree into R2 under ``--prefix``
(default ``data``), which is exactly the key layout the Next.js app reads when
``ENV=prod`` (see ``web/lib/data/storage.ts`` + ``lib/server/dataKeys.ts``).

Credentials and target come from env (or flags):
    R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET

Safety features:
  * ``--dry-run``           : list actions, write nothing.
  * ETag (MD5) change-skip  : unchanged objects are not re-uploaded.
  * runtime-owned prefixes  : keys the running app writes (users, adjustments,
                              budgets, annotations) are never uploaded or
                              deleted, so a demo push can't clobber prod state.

Usage:
    python scripts/push_to_r2.py --dry-run
    R2_ACCOUNT_ID=... R2_ACCESS_KEY_ID=... R2_SECRET_ACCESS_KEY=... \
        R2_BUCKET=app-financial-cockpit python scripts/push_to_r2.py
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

try:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover
    sys.exit("boto3 is required: pip install boto3")

# Local datastore relative to this script (../web/data).
LOCAL_DATA_DIR = (Path(__file__).resolve().parent.parent / "web" / "data").resolve()

# Prefixes the live app owns at runtime — never overwrite or delete these so a
# local seed push can't wipe production user data.
RUNTIME_OWNED_PREFIXES = (
    "globals/users.json",
    "globals/pnl/",
    "user_annotations/",
)


def is_runtime_owned(rel_key: str) -> bool:
    return any(
        rel_key == p or rel_key.startswith(p) for p in RUNTIME_OWNED_PREFIXES
    )


def md5_hex(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def make_client(account_id: str, access_key: str, secret_key: str):
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
        region_name="auto",
    )


def remote_etag(client, bucket: str, key: str) -> str | None:
    try:
        head = client.head_object(Bucket=bucket, Key=key)
        return head.get("ETag", "").strip('"')
    except ClientError:
        return None


def iter_local_files(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_file():
            yield path, path.relative_to(root).as_posix()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="list actions, write nothing")
    parser.add_argument("--prefix", default=os.environ.get("R2_DATA_PREFIX", "data"),
                        help="R2 key prefix (default: data)")
    parser.add_argument("--account-id", default=os.environ.get("R2_ACCOUNT_ID", ""))
    parser.add_argument("--access-key-id", default=os.environ.get("R2_ACCESS_KEY_ID", ""))
    parser.add_argument("--secret-access-key", default=os.environ.get("R2_SECRET_ACCESS_KEY", ""))
    parser.add_argument("--bucket", default=os.environ.get("R2_BUCKET", "app-financial-cockpit"))
    args = parser.parse_args()

    if not LOCAL_DATA_DIR.is_dir():
        return f"local data dir not found: {LOCAL_DATA_DIR}"

    files = list(iter_local_files(LOCAL_DATA_DIR))
    print(f"Local datastore : {LOCAL_DATA_DIR}  ({len(files)} files)")
    print(f"Target          : r2://{args.bucket}/{args.prefix}/")
    print(f"Mode            : {'DRY RUN' if args.dry_run else 'LIVE'}\n")

    client = None
    if not args.dry_run:
        missing = [n for n, v in (
            ("R2_ACCOUNT_ID", args.account_id),
            ("R2_ACCESS_KEY_ID", args.access_key_id),
            ("R2_SECRET_ACCESS_KEY", args.secret_access_key),
        ) if not v]
        if missing:
            return f"missing credentials: {', '.join(missing)}"
        client = make_client(args.account_id, args.access_key_id, args.secret_access_key)

    uploaded = skipped = protected = 0
    for path, rel_key in files:
        if is_runtime_owned(rel_key):
            protected += 1
            print(f"  protect  {rel_key}  (runtime-owned, skipped)")
            continue

        object_key = f"{args.prefix}/{rel_key}"
        data = path.read_bytes()

        if args.dry_run:
            uploaded += 1
            print(f"  upload   {rel_key}  ->  {object_key}")
            continue

        if remote_etag(client, args.bucket, object_key) == md5_hex(data):
            skipped += 1
            continue
        client.put_object(Bucket=args.bucket, Key=object_key, Body=data)
        uploaded += 1
        print(f"  upload   {rel_key}  ->  {object_key}")

    print(f"\nDone. {uploaded} to upload, {skipped} unchanged, {protected} runtime-owned.")
    if args.dry_run:
        print("Dry run — nothing was written. Re-run without --dry-run to push.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
