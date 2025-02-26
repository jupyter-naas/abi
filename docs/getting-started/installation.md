# Installation Guide

This guide provides detailed instructions for installing ABI in different environments.

## System Requirements

- **Operating System**: Linux, macOS, or Windows with WSL
- **Python**: 3.8 or higher
- **RAM**: Minimum 8GB, recommended 16GB
- **Storage**: At least 2GB of free disk space

## Installation Methods

### Method 1: Standard Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/abi.git
cd abi

# Create and activate a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Method 2: Development Installation

If you plan to contribute to ABI, install it in development mode:

```bash
# Clone the repository
git clone https://github.com/yourusername/abi.git
cd abi

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"
```

### Method 3: Docker Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/abi.git
cd abi

# Build the Docker image
docker build -t abi:latest .

# Run the container
docker run -p 8000:8000 -v $(pwd):/app abi:latest
```

## Post-Installation Setup

1. **Environment Variables**

   Copy the example environment file and update it with your settings:

   ```bash
   cp .env.example .env
   # Edit .env with your editor of choice
   ```

2. **Database Setup**

   Initialize the database:

   ```bash
   python scripts/init_db.py
   ```

3. **Verify Installation**

   Run the verification script to ensure everything is working:

   ```bash
   python scripts/verify_installation.py
   ```

## Troubleshooting

### Common Issues

1. **Dependency Conflicts**

   If you encounter dependency conflicts, try creating a fresh virtual environment:

   ```bash
   rm -rf venv
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Permission Issues**

   On Linux/macOS, if you encounter permission issues:

   ```bash
   chmod +x scripts/*.py
   ```

## Next Steps

- Continue to the [Configuration Guide](configuration.md)
- Check the [Quick Start Guide](quick-start.md) to run your first ABI process 