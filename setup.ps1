# ABI Windows Setup Script (PowerShell)
Write-Host "🚀 Setting up ABI (Agentic Brain Infrastructure) on Windows..." -ForegroundColor Green

# Check if Python is installed
try {
    $pythonVersion = python --version 2>$null
    Write-Host "✅ Found Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python is not installed or not in PATH" -ForegroundColor Red
    Write-Host "📚 Please install Python from https://python.org" -ForegroundColor Yellow
    exit 1
}

# Check if uv is installed
try {
    $uvVersion = uv --version 2>$null
    Write-Host "✅ Found uv: $uvVersion" -ForegroundColor Green
} catch {
    Write-Host "🚀 Installing uv (Python package manager)..." -ForegroundColor Yellow
    pip install uv
}

# Create virtual environment
Write-Host "📦 Creating virtual environment..." -ForegroundColor Cyan
uv venv

# Install dependencies
Write-Host "📚 Installing dependencies..." -ForegroundColor Cyan
& ".venv\Scripts\Activate.ps1"
uv pip install -e lib/

# Create config from example if it doesn't exist
if (-not (Test-Path "config.yaml")) {
    Write-Host "⚙️ Creating config.yaml from example..." -ForegroundColor Cyan
    Copy-Item "config.yaml.example" "config.yaml"
}

# Create .env from example if it doesn't exist
if (-not (Test-Path ".env")) {
    Write-Host "🔐 Creating .env file..." -ForegroundColor Cyan
    @"
# ABI Environment Variables
FIRST_NAME=YourFirstName
LAST_NAME=YourLastName
EMAIL=your.email@example.com
ENV=dev
AI_MODE=local
LOG_LEVEL=INFO
ABI_API_KEY=your-api-key-here

# Add your API keys below:
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
# MISTRAL_API_KEY=...
# XAI_API_KEY=xai-...
# PERPLEXITY_API_KEY=pplx-...
# Add other API keys as needed
"@ | Out-File -FilePath ".env" -Encoding UTF8
}

# Create missing storage directories
Write-Host "📁 Creating storage directories..." -ForegroundColor Cyan
$storageDirs = @("storage", "storage\datastore", "storage\triplestore", "storage\vectorstore", "storage\cache")
foreach ($dir in $storageDirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}

# Check for example data
if (Test-Path "storage\datastore\example") {
    Write-Host "📋 Example data found in storage\datastore\example" -ForegroundColor Green
}
if (Test-Path "storage\triplestore\example") {
    Write-Host "📋 Example ontologies found in storage\triplestore\example" -ForegroundColor Green
}

Write-Host "`n✅ Setup complete!" -ForegroundColor Green
Write-Host "`n🎯 Next steps:" -ForegroundColor Yellow
Write-Host "1. Edit .env file with your API keys"
Write-Host "2. Edit config.yaml to customize your setup"
Write-Host "3. Run: .venv\Scripts\Activate.ps1"
Write-Host "4. Start API: python src\api.py"
Write-Host "5. Or start MCP server: python mcp_server.py"
Write-Host "`n📚 Documentation: docs\get_started.md"
Write-Host "🌐 API Docs (after starting): http://localhost:9879/docs" -ForegroundColor Cyan
