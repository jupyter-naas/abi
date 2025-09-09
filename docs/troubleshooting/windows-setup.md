# Windows Setup Troubleshooting

This guide helps resolve common issues when setting up ABI on Windows.

## Common Issues

### Issue 1: Missing `src` and `storage` directories after cloning

**Symptoms:**
- After `git clone`, the `src/` or `storage/` directories are missing or empty
- Error messages about missing modules or files

**Root Cause:**
The `storage/` directory structure is managed by DVC (Data Version Control) and `.gitignore` rules. Most storage content is not included in the Git repository to keep it lightweight.

**Solution:**
Run the automated setup script which creates the necessary directory structure:

```cmd
setup.bat
```

Or manually create the directories:
```cmd
mkdir storage
mkdir storage\datastore
mkdir storage\triplestore
mkdir storage\vectorstore
mkdir storage\cache
```

### Issue 2: "make: command not found"

**Symptoms:**
- Error when trying to run `make` commands from documentation
- `'make' is not recognized as an internal or external command`

**Root Cause:**
Windows doesn't include the `make` utility by default. The project's `Makefile` is designed for Unix-like systems.

**Solutions:**

**Option 1: Use the Windows setup scripts (Recommended)**
```cmd
# Instead of 'make deps'
setup.bat

# Instead of 'make api' 
python src\api.py

# Instead of 'make mcp'
python mcp_server.py
```

**Option 2: Install make for Windows**
- Install [Chocolatey](https://chocolatey.org/install) package manager
- Run: `choco install make`
- Or install [Git for Windows](https://git-scm.com/download/win) which includes make

**Option 3: Use PowerShell equivalents**
```powershell
# Instead of make commands, use direct Python calls
python src\api.py          # Start API server
python mcp_server.py       # Start MCP server
python -m pytest tests/   # Run tests
```

### Issue 3: Python/uv not found

**Symptoms:**
- `'python' is not recognized as an internal or external command`
- `'uv' is not recognized as an internal or external command`

**Solutions:**

**For Python:**
1. Install Python from [python.org](https://python.org)
2. During installation, check "Add Python to PATH"
3. Restart your terminal/command prompt

**For uv:**
```cmd
# Install uv using pip
pip install uv

# Or install using PowerShell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Issue 4: Permission errors

**Symptoms:**
- "Access denied" errors when creating files or directories
- Scripts fail to create `.env` or `config.yaml`

**Solutions:**
1. Run Command Prompt or PowerShell as Administrator
2. Or ensure you have write permissions in the project directory
3. Check if antivirus software is blocking file creation

### Issue 5: Virtual environment activation fails

**Symptoms:**
- `.venv\Scripts\activate.bat` doesn't work
- PowerShell execution policy errors

**Solutions:**

**For Command Prompt:**
```cmd
# Use full path
.venv\Scripts\activate.bat

# Or navigate to the directory first
cd .venv\Scripts
activate.bat
cd ..\..
```

**For PowerShell:**
```powershell
# Set execution policy (run as Administrator)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Then activate
.venv\Scripts\Activate.ps1
```

### Issue 6: Missing API keys

**Symptoms:**
- Agents return authentication errors
- "API key not found" messages

**Solution:**
1. Edit the `.env` file created by the setup script
2. Add your actual API keys:
```
OPENAI_API_KEY=sk-your-actual-key-here
ANTHROPIC_API_KEY=sk-ant-your-actual-key-here
# Add other keys as needed
```
3. Restart the API server after updating keys

## Windows-Specific Commands

Here are Windows equivalents for common Unix commands used in the documentation:

| Unix Command | Windows Command | Description |
|--------------|-----------------|-------------|
| `make deps` | `setup.bat` | Install dependencies |
| `make api` | `python src\api.py` | Start API server |
| `make mcp` | `python mcp_server.py` | Start MCP server |
| `cp file1 file2` | `copy file1 file2` | Copy files |
| `ls` | `dir` | List directory contents |
| `cat file` | `type file` | Display file contents |
| `export VAR=value` | `set VAR=value` | Set environment variable |

## Getting Help

If you're still experiencing issues:

1. Check the main [troubleshooting guide](../troubleshooting/)
2. Review the [getting started guide](../get_started.md)
3. Open an issue on [GitHub](https://github.com/jupyter-naas/abi/issues) with:
   - Your Windows version
   - Python version (`python --version`)
   - Complete error messages
   - Steps you've already tried
