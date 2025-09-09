@echo off
REM ABI Windows Setup Script
echo 🚀 Setting up ABI (Agentic Brain Infrastructure) on Windows...

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python is not installed or not in PATH
    echo 📚 Please install Python from https://python.org
    exit /b 1
)

REM Check if uv is installed
uv --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 🚀 Installing uv (Python package manager)...
    pip install uv
)

REM Create virtual environment
echo 📦 Creating virtual environment...
uv venv

REM Activate virtual environment and install dependencies
echo 📚 Installing dependencies...
call .venv\Scripts\activate.bat
uv pip install -e lib/

REM Create config from example if it doesn't exist
if not exist config.yaml (
    echo ⚙️ Creating config.yaml from example...
    copy config.yaml.example config.yaml
)

REM Create .env from example if it doesn't exist  
if not exist .env (
    echo 🔐 Creating .env file...
    echo # ABI Environment Variables > .env
    echo FIRST_NAME=YourFirstName >> .env
    echo LAST_NAME=YourLastName >> .env
    echo EMAIL=your.email@example.com >> .env
    echo ENV=dev >> .env
    echo AI_MODE=local >> .env
    echo LOG_LEVEL=INFO >> .env
    echo ABI_API_KEY=your-api-key-here >> .env
    echo # Add your API keys below: >> .env
    echo # OPENAI_API_KEY=sk-... >> .env
    echo # ANTHROPIC_API_KEY=sk-ant-... >> .env
    echo # Add other API keys as needed >> .env
)

REM Create missing storage directories
echo 📁 Creating storage directories...
if not exist storage mkdir storage
if not exist storage\datastore mkdir storage\datastore
if not exist storage\triplestore mkdir storage\triplestore  
if not exist storage\vectorstore mkdir storage\vectorstore
if not exist storage\cache mkdir storage\cache

REM Copy example data if it exists
if exist storage\datastore\example (
    echo 📋 Example data found in storage\datastore\example
)
if exist storage\triplestore\example (
    echo 📋 Example ontologies found in storage\triplestore\example  
)

echo ✅ Setup complete!
echo.
echo 🎯 Next steps:
echo 1. Edit .env file with your API keys
echo 2. Edit config.yaml to customize your setup
echo 3. Run: .venv\Scripts\activate.bat
echo 4. Start API: python src\api.py
echo 5. Or start MCP server: python mcp_server.py
echo.
echo 📚 Documentation: docs\get_started.md
echo 🌐 API Docs (after starting): http://localhost:9879/docs
