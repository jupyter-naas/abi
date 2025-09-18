# Code-Data Symmetry

## The Rule

**Every code component has a mirror folder in `storage/datastore/`**

```
src/core/your_module/orchestration/    →    storage/datastore/core/modules/your_module/orchestration/
src/core/your_module/pipelines/        →    storage/datastore/core/modules/your_module/pipelines/
```

**Why?** No hunting for data. No root pollution. Clean scaling.

## Quick Start

### 1. Create Module Structure
```bash
# Code (manual)
mkdir -p src/core/your_module/{orchestration,pipelines,workflows}

# Data (automatic - your code creates it!)
# No manual mkdir needed - use os.makedirs(path, exist_ok=True)
```

### 2. Auto-Create Data Directories
```python
# Option 1: Use ABI utility (recommended)
from abi.utils.Storage import ensure_data_directory

data_dir = ensure_data_directory("your_module", "orchestration")
# Creates: storage/datastore/core/modules/your_module/orchestration/

# Option 2: Manual (also works)
import os
data_dir = "storage/datastore/core/modules/your_module/orchestration"
os.makedirs(data_dir, exist_ok=True)

# Then use it:
with open(os.path.join(data_dir, "output.txt"), "w") as f:
    f.write("data")
```

### 3. Configure Components
```bash
# Orchestration uses its data folder
DAGSTER_HOME=$(PWD)/storage/datastore/core/modules/your_module/orchestration
```

## Examples

### Orchestration
```python
# src/core/your_module/orchestration/definitions.py
from abi.utils.Storage import ensure_data_directory

@dagster.asset
def my_asset():
    data_dir = ensure_data_directory("your_module", "orchestration")
    
    with open(os.path.join(data_dir, "output.json"), "w") as f:
        f.write('{"status": "complete"}')
```

### Pipelines
```python
# src/core/your_module/pipelines/YourPipeline.py
from abi.utils.Storage import ensure_data_directory

class YourPipeline:
    def run(self, params):
        output_dir = ensure_data_directory("your_module", "pipelines")
        
        # Process and save RDF graph
        graph.serialize(os.path.join(output_dir, "result.ttl"))
```

### Integrations
```python
# src/core/your_module/integrations/YourIntegration.py
from abi.utils.Storage import ensure_data_directory

class YourIntegration:
    def fetch_data(self):
        cache_dir = ensure_data_directory("your_module", "integrations")
        
        # Cache API response
        with open(os.path.join(cache_dir, "response.json"), "w") as f:
            f.write(api_response)
```

## Rules

### ✅ Do This
```python
# Use ABI utility (recommended)
from abi.utils.Storage import ensure_data_directory
data_dir = ensure_data_directory("your_module", "orchestration")

# Or manual (also works)
os.makedirs("storage/datastore/core/modules/your_module/component", exist_ok=True)
```

```bash
# Always use absolute paths in config
DAGSTER_HOME=$(PWD)/storage/datastore/core/modules/your_module/orchestration

# Mirror every code component
src/core/demo/pipelines/ → storage/datastore/core/modules/demo/pipelines/
```

### ❌ Don't Do This
```bash
# Manual directory creation (fragile)
mkdir -p storage/datastore/...

# Relative paths (break things)
DAGSTER_HOME=storage/orchestration

# Root pollution (messy)
./temp_files/
./my_data.db
```

## Troubleshooting

### Check Structure
```bash
# Verify both sides exist
tree src/core/your_module
tree storage/datastore/core/modules/your_module

# Find root pollution
find . -maxdepth 1 -name "tmp*" -o -name "*.db" -o -name "*.log"
```

### Fix Existing Module
```bash
# 1. Find scattered data
find . -name "*.db" -o -name "*.log" | grep -v storage/datastore

# 2. Create proper structure  
mkdir -p storage/datastore/core/modules/your_module/orchestration

# 3. Move data
mv scattered_file.db storage/datastore/core/modules/your_module/orchestration/

# 4. Update config
# Change: DAGSTER_HOME=temp_dir
# To:     DAGSTER_HOME=$(PWD)/storage/datastore/core/modules/your_module/orchestration
```

## Reference

See `src/core/__demo__/` for a working example of Code-Data Symmetry.
