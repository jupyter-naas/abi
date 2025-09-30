# Embedding Dimension Mismatch

## Error
```
ValueError: could not broadcast input array from shape (768,) into shape (1536,)
```

## Fix
```bash
rm -rf storage/cache/intent_mapping/*
make
```

## Why This Happens
The system auto-detects embedding dimensions in `lib/abi/services/agent/beta/IntentMapper.py`:

```python
# Tests actual embedding to get real dimensions
test_embedding = embeddings(intents_values[0])
dimension = len(test_embedding)
```

But old cached embeddings from a different `AI_MODE` can conflict. Clearing cache forces fresh detection.
