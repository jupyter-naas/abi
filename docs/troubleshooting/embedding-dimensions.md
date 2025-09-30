# Embedding Dimensions Fix

## Problem

The system was experiencing dimension mismatch errors when switching between embedding providers:

```
ValueError: could not broadcast input array from shape (768,) into shape (1536,)
```

This occurred because:
- **Vector stores** were initialized with hardcoded dimensions based on environment variables
- **Actual embeddings** at runtime could have different dimensions
- **Cache conflicts** between different embedding providers

## Root Cause

1. **Environment-based dimension detection** was unreliable
2. **Single cache** mixed embeddings from different providers
3. **Cached vector stores** retained wrong dimensions after provider changes

## Solution

### 1. Auto-Detection of Embedding Dimensions

**Before:**
```python
# Brittle - relies on environment being set correctly
dimension = 768 if os.environ.get('AI_MODE') == "airgap" else 1536
```

**After:**
```python
# Robust - tests actual embedding output
test_embedding = embeddings(intents_values[0])
dimension = len(test_embedding)  # Auto-detects: 768, 1536, or any future size
```

### 2. Provider-Specific Caching

**Before:**
```
storage/cache/intent_mapping/
├── abc123... (mixed dimensions - CONFLICT!)
└── def456... (could be 768 OR 1536 - BROKEN!)
```

**After:**
```
storage/cache/intent_mapping/
├── openai_1536/     (OpenAI embeddings only)
│   └── abc123...    (guaranteed 1536 dimensions)
└── airgap_768/      (Local embeddings only)
    └── def456...    (guaranteed 768 dimensions)
```

## Benefits

### Performance
- **Zero cache clearing** needed when switching providers
- **Preserved embeddings** when switching back and forth
- **Instant provider switching** without re-computation

### Reliability
- **Impossible dimension conflicts** - each provider isolated
- **Auto-adaptation** to any embedding provider
- **Future-proof** for new providers with different dimensions

### Developer Experience
- **Clear debugging** - know which cache belongs to which provider
- **No manual intervention** required
- **Works regardless** of environment variable configuration

## Implementation Details

### Files Modified

1. **`lib/abi/services/agent/beta/IntentMapper.py`**
   - Added auto-detection of embedding dimensions
   - Tests actual embedding output instead of trusting environment variables
   - Maintains fallback for edge cases

2. **`lib/abi/services/agent/beta/Embeddings.py`**
   - Implemented provider-specific cache directories
   - Separated OpenAI and airgap caches completely
   - Prevents cross-contamination between providers

### Cache Structure

- **OpenAI Provider**: `storage/cache/intent_mapping/openai_1536/`
- **Airgap Provider**: `storage/cache/intent_mapping/airgap_768/`
- **Future Providers**: Easy to add new directories

## Testing

The fix has been tested with:
- ✅ OpenAI embeddings (1536 dimensions)
- ✅ Local airgap embeddings (768 dimensions)  
- ✅ Provider switching without cache conflicts
- ✅ Auto-detection working correctly
- ✅ Performance maintained across switches

## Troubleshooting

### If you still see dimension errors:

1. **Clear old mixed cache:**
   ```bash
   rm -rf storage/cache/intent_mapping/*
   ```

2. **Restart the system:**
   ```bash
   make
   ```

3. **Check debug output:**
   Look for: `🔍 Detected embedding dimension: 1536`

### Verification Commands

```bash
# Check cache structure
ls -la storage/cache/intent_mapping/

# Test dimension detection
python -c "
from lib.abi.services.agent.beta.Embeddings import embeddings
result = embeddings('test')
print('Detected dimension:', len(result))
"
```

## Future Enhancements

This architecture supports:
- **Multiple embedding models** per provider
- **Custom dimension sizes** for new providers
- **Hybrid deployments** with multiple providers active
- **A/B testing** between embedding providers
