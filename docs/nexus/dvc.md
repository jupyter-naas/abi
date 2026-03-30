# Data Version Control (DVC + MinIO)

> **Status: partial — work in progress**
>
> DVC is initialized and MinIO is configured. Smaller datasets are uploaded and
> tracked. The two largest datasets (`src/notion` 2.4 GB, `src/iphone-jrv` 2.3 GB)
> hit disk I/O errors during upload — likely MinIO being overloaded after
> processing ~5 GB back-to-back. Resume when MinIO has had time to recover,
> or split uploads across sessions (see [Resuming below](#resuming)).

All large data is versioned with [DVC](https://dvc.org) and stored in the local
MinIO instance (`s3://aia-dvc`). Git tracks tiny `.dvc` pointer files; MinIO
holds the actual bytes.

## Remote

| Property | Value |
|----------|-------|
| Name | `minio` (default) |
| Bucket | `s3://aia-dvc` |
| Endpoint | `http://localhost:9000` |
| Credentials | `~/.aia/.dvc/config.local` (gitignored) |

## Tracked datasets

| `.dvc` file | Source | Size |
|-------------|--------|------|
| `src/qonto.dvc` | Qonto financial exports | ~245 MB |
| `src/fmz-engagement.dvc` | FMZ engagement data | ~887 MB |
| `src/chatgpt.dvc` | ChatGPT/OpenAI exports | ~1.1 GB |
| `src/notion.dvc` | Notion workspace export | ~2.4 GB |
| `src/iphone-jrv.dvc` | iPhone data export | ~2.3 GB |
| `src/obsidian.dvc` | Obsidian vault | ~1.2 GB |
| `src/wikileaks/data.dvc` | WikiLeaks search cache | ~25 MB |
| `src/cursor/data.dvc` | Cursor DB & exports | ~59 MB |
| `src/abi-app/data.dvc` | ABI app data | ~50 MB |
| `src/cuas/data.dvc` | CUAS collected data | ~313 MB |
| `src/transcription/data.dvc` | Transcription DB | ~108 MB |
| `src/transcription/apps/whisper/backend/whisper-models.dvc` | Whisper ML models | ~282 MB |

## Common commands

```bash
# Pull all data locally after cloning
dvc pull

# Pull a single dataset
dvc pull src/notion.dvc

# Push local changes to MinIO
dvc push

# Check what's out of sync
dvc status --cloud

# Add a new data directory
dvc add src/new-data --to-remote
git add src/new-data.dvc src/new-data/.gitignore
git commit -m "data: track new-data with DVC"

# Update an existing dataset (after modifying files)
dvc add src/notion --to-remote
git add src/notion.dvc
git commit -m "data(notion): update export YYYY-MM-DD"
dvc push
```

## Workflow for a new machine

```bash
# 1. Clone repo (gets .dvc pointer files, no data)
git clone --recurse-submodules https://github.com/jravenel/aia.git
cd aia

# 2. Add MinIO credentials to local DVC config (gitignored)
dvc remote modify --local minio access_key_id YOUR_KEY
dvc remote modify --local minio secret_access_key YOUR_SECRET

# 3. Pull the data you need
dvc pull src/cursor/data.dvc   # just cursor
dvc pull                        # everything
```

## MinIO UI

Browse data at **http://localhost:9001** (minioadmin / minioadmin)  
Bucket: `aia-dvc` → `files/`

---

## Resuming

When ready to finish tracking the two remaining large datasets:

```bash
# 1. Make sure MinIO is healthy
docker ps --filter name=minio
curl -s http://localhost:9000/minio/health/live && echo "OK"

# 2. Re-add credentials if lost
dvc remote modify --local minio access_key_id minioadmin
dvc remote modify --local minio secret_access_key minioadmin

# 3. Upload one at a time — don't run in parallel (DVC single-lock)
dvc add src/notion --to-remote
dvc add src/iphone-jrv --to-remote

# 4. Commit the pointer files
git add src/notion.dvc src/iphone-jrv.dvc
git commit -m "data: track notion and iphone-jrv with DVC"
```

**Known issue**: uploading multiple multi-GB directories back-to-back causes
MinIO to return `Access Denied` / disk I/O errors. Upload in separate terminal
sessions with a break in between, or restart MinIO first:

```bash
docker restart aia-minio-1
# wait ~10s for healthy status, then run dvc add
```
