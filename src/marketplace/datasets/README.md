# ABI Marketplace Datasets

This directory contains curated datasets that can be used by marketplace applications, domain experts, and AI agents for analysis, training, and demonstration purposes.

## Dataset Categories

### 📊 Business
- Company information and metrics
- Market data and trends
- Industry benchmarks
- Customer analytics

### 💰 Finance
- Stock market data
- Economic indicators
- Financial statements
- Trading data

### 🔬 Technology
- Tech company data
- Software metrics
- AI/ML benchmarks
- Development statistics

### 📚 Research
- Academic papers metadata
- Research trends
- Citation networks
- Scientific datasets

### 🎯 Samples
- Demo datasets for testing
- Tutorial data
- Example use cases
- Template datasets

## Dataset Format Standards

### File Formats
- **CSV**: Tabular data with headers
- **JSON**: Structured data and metadata
- **JSONL**: Line-delimited JSON for large datasets
- **Parquet**: Optimized columnar data (for large datasets)

### Metadata Requirements
Each dataset should include:
- `metadata.json`: Dataset description, schema, source, license
- `README.md`: Usage instructions and examples
- `schema.json`: Data schema definition (optional)

### Example Metadata Structure
```json
{
  "name": "sample_companies",
  "description": "Sample company data for demos",
  "version": "1.0.0",
  "created": "2024-01-01",
  "updated": "2024-01-01",
  "source": "Generated for ABI demos",
  "license": "MIT",
  "format": "csv",
  "size": "1.2MB",
  "rows": 1000,
  "columns": 8,
  "tags": ["business", "companies", "demo"],
  "schema": {
    "company_name": "string",
    "industry": "string",
    "employees": "integer",
    "revenue": "float",
    "founded": "date",
    "location": "string",
    "website": "string",
    "description": "text"
  }
}
```

## Usage in Applications

### Python (Pandas)
```python
import pandas as pd
import os

# Load dataset
dataset_path = "src/marketplace/datasets/business/companies.csv"
df = pd.read_csv(dataset_path)

# Use in analysis
print(df.head())
```

### Streamlit Apps
```python
import streamlit as st
import pandas as pd

@st.cache_data
def load_dataset(path):
    return pd.read_csv(path)

# In your app
df = load_dataset("src/marketplace/datasets/finance/stocks.csv")
st.dataframe(df)
```

### AI Agents
Agents can reference datasets for:
- Data analysis tasks
- Generating insights
- Creating visualizations
- Training examples

## Contributing Datasets

1. Choose appropriate category folder
2. Add dataset files (CSV, JSON, etc.)
3. Include `metadata.json` with complete information
4. Add `README.md` with usage examples
5. Ensure data is clean and well-formatted
6. Test with sample applications

## Data Privacy & Licensing

- Only include public domain or properly licensed data
- No personal or sensitive information
- Clearly document data sources and licenses
- Follow GDPR and privacy best practices
- Use synthetic data for demos when possible
