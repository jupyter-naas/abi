"""Upload X Next.js static export to object storage (MinIO)."""
from __future__ import annotations

import mimetypes
import sys
from pathlib import Path

EXPORT_DIR = Path(
    "/app/.abi/libs/naas-abi-marketplace/naas_abi_marketplace"
    "/applications/x/apps/x/web/out"
)
LOCAL_MIRROR = Path("/app/.abi/storage/datastore/x/apps/x")
APP_PREFIX = "x/apps/x"


def main() -> int:
    if not (EXPORT_DIR / "index.html").is_file():
        print(f"missing export at {EXPORT_DIR}", file=sys.stderr)
        return 1

    # Load secrets via Engine config without importing application modules.
    from naas_abi_core.engine.Engine import Engine

    config_path = Path("/app/config.local.yaml")
    if not config_path.exists():
        config_path = Path("/app/.abi/config.local.yaml")
    engine = Engine(configuration=config_path.read_text())
    # Minimal load — services only. Avoid marketplace module init.
    engine.load(module_names=[])
    storage = engine.services.object_storage

    uploaded = 0
    for path in sorted(EXPORT_DIR.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(EXPORT_DIR).as_posix()
        if rel in {"404.html", "index.txt"} or rel.startswith("404/"):
            continue
        if "/" in rel:
            subdir, name = rel.rsplit("/", 1)
            prefix = f"{APP_PREFIX}/{subdir}"
        else:
            prefix = APP_PREFIX
            name = rel
        content = path.read_bytes()
        storage.put_object(prefix, name, content)
        dest = LOCAL_MIRROR / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        uploaded += 1

    raw = storage.get_object(APP_PREFIX, "index.html")
    print(f"uploaded {uploaded} files under {APP_PREFIX}/")
    print(f"index bytes={len(raw)} has_next={b'_next' in raw}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
