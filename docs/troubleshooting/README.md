# Troubleshooting

## Error Messages

| Error | Fix |
|-------|-----|
| `Port already in use` | `lsof -tiTCP:5432,7878,3000 -sTCP:LISTEN \| xargs -r kill -9 && make dev-up` |
| `Cannot connect to Docker daemon` | Open Docker Desktop, wait 30 seconds |
| `could not broadcast input array from shape (768,) into shape (1536,)` | `rm -rf storage/cache/intent_mapping/* && make` |
| `Application crashed due to agent loading failure` | Usually cache issue - clear cache above |

## Docker Issues
See [docker-conflicts.md](docker-conflicts.md) for detailed Docker troubleshooting.
