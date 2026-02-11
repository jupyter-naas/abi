#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NEXUS_REPO="https://github.com/jravenel/nexus.git"
NEXUS_DIR="${NEXUS_HOME:-$HOME/nexus}"
MIN_NODE_VERSION=18
MIN_PYTHON_VERSION=3.11

echo -e "${BLUE}"
echo "  _   _ _______  ___   _ ____  "
echo " | \ | | ____\ \/ / | | / ___| "
echo " |  \| |  _|  \  /| | | \___ \ "
echo " | |\  | |___ /  \| |_| |___) |"
echo " |_| \_|_____/_/\_\\\\___/|____/ "
echo -e "${NC}"
echo "The AI-powered knowledge platform by naas.ai"
echo ""

# Detect OS
detect_os() {
    case "$(uname -s)" in
        Darwin*)    OS="macos" ;;
        Linux*)     OS="linux" ;;
        MINGW*|MSYS*|CYGWIN*) OS="windows" ;;
        *)          OS="unknown" ;;
    esac
    echo -e "${GREEN}Detected OS:${NC} $OS"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Version comparison
version_gte() {
    [ "$(printf '%s\n' "$1" "$2" | sort -V | head -n1)" = "$2" ]
}

# Check Node.js
check_node() {
    if command_exists node; then
        NODE_VERSION=$(node -v | sed 's/v//')
        if version_gte "$NODE_VERSION" "$MIN_NODE_VERSION"; then
            echo -e "${GREEN}✓${NC} Node.js $NODE_VERSION"
            return 0
        else
            echo -e "${RED}✗${NC} Node.js $NODE_VERSION (need >= $MIN_NODE_VERSION)"
            return 1
        fi
    else
        echo -e "${RED}✗${NC} Node.js not found"
        return 1
    fi
}

# Check Python
check_python() {
    local PYTHON_CMD=""
    if command_exists python3; then
        PYTHON_CMD="python3"
    elif command_exists python; then
        PYTHON_CMD="python"
    fi
    
    if [ -n "$PYTHON_CMD" ]; then
        PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        if version_gte "$PYTHON_VERSION" "$MIN_PYTHON_VERSION"; then
            echo -e "${GREEN}✓${NC} Python $PYTHON_VERSION"
            return 0
        else
            echo -e "${RED}✗${NC} Python $PYTHON_VERSION (need >= $MIN_PYTHON_VERSION)"
            return 1
        fi
    else
        echo -e "${RED}✗${NC} Python not found"
        return 1
    fi
}

# Check pnpm
check_pnpm() {
    if command_exists pnpm; then
        PNPM_VERSION=$(pnpm -v)
        echo -e "${GREEN}✓${NC} pnpm $PNPM_VERSION"
        return 0
    else
        echo -e "${YELLOW}!${NC} pnpm not found (will install)"
        return 1
    fi
}

# Check uv
check_uv() {
    if command_exists uv; then
        UV_VERSION=$(uv --version | awk '{print $2}')
        echo -e "${GREEN}✓${NC} uv $UV_VERSION"
        return 0
    else
        echo -e "${YELLOW}!${NC} uv not found (will install)"
        return 1
    fi
}

# Check Git
check_git() {
    if command_exists git; then
        GIT_VERSION=$(git --version | awk '{print $3}')
        echo -e "${GREEN}✓${NC} Git $GIT_VERSION"
        return 0
    else
        echo -e "${RED}✗${NC} Git not found"
        return 1
    fi
}

# Install pnpm if needed
install_pnpm() {
    echo -e "${BLUE}Installing pnpm...${NC}"
    if command_exists npm; then
        npm install -g pnpm
    else
        curl -fsSL https://get.pnpm.io/install.sh | sh -
    fi
}

# Install uv if needed
install_uv() {
    echo -e "${BLUE}Installing uv...${NC}"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
}

# Main installation
install_nexus() {
    echo ""
    echo -e "${BLUE}Checking prerequisites...${NC}"
    echo ""
    
    PREREQ_OK=true
    
    check_git || PREREQ_OK=false
    check_node || PREREQ_OK=false
    check_python || PREREQ_OK=false
    check_pnpm || install_pnpm
    check_uv || install_uv
    
    if [ "$PREREQ_OK" = false ]; then
        echo ""
        echo -e "${RED}Missing prerequisites. Please install them first:${NC}"
        echo ""
        echo "  Node.js >= 18: https://nodejs.org/"
        echo "  Python >= 3.11: https://python.org/"
        echo "  Git: https://git-scm.com/"
        echo ""
        exit 1
    fi
    
    echo ""
    echo -e "${BLUE}Installing NEXUS to ${NEXUS_DIR}...${NC}"
    echo ""
    
    # Clone or update repository
    if [ -d "$NEXUS_DIR" ]; then
        echo "Updating existing installation..."
        cd "$NEXUS_DIR"
        git pull origin master
    else
        echo "Cloning repository..."
        git clone "$NEXUS_REPO" "$NEXUS_DIR"
        cd "$NEXUS_DIR"
    fi
    
    # Install Node dependencies
    echo ""
    echo -e "${BLUE}Installing Node.js dependencies...${NC}"
    pnpm install
    
    # Set up Python backend with uv
    echo ""
    echo -e "${BLUE}Setting up Python backend with uv...${NC}"
    cd apps/api
    
    # Ensure uv is in PATH
    export PATH="$HOME/.cargo/bin:$PATH"
    
    # Sync dependencies with uv
    uv sync
    
    cd "$NEXUS_DIR"
    
    # Create .env files if they don't exist
    if [ ! -f "apps/api/.env" ]; then
        cp apps/api/.env.example apps/api/.env 2>/dev/null || true
    fi
    
    # Create launcher script
    mkdir -p "$HOME/.local/bin"
    cat > "$HOME/.local/bin/nexus" << 'LAUNCHER'
#!/bin/bash
NEXUS_DIR="${NEXUS_HOME:-$HOME/nexus}"
cd "$NEXUS_DIR"

case "$1" in
    start|dev)
        pnpm dev
        ;;
    build)
        pnpm build
        ;;
    update)
        git pull origin master && pnpm install
        ;;
    api)
        cd apps/api
        export PATH="$HOME/.cargo/bin:$PATH"
        uv run pnpm dev
        ;;
    web)
        pnpm --filter web dev
        ;;
    *)
        echo "NEXUS - The AI-powered knowledge platform"
        echo ""
        echo "Usage: nexus <command>"
        echo ""
        echo "Commands:"
        echo "  start, dev    Start development server"
        echo "  build         Build for production"
        echo "  update        Update to latest version"
        echo "  api           Start API server only"
        echo "  web           Start web frontend only"
        echo ""
        ;;
esac
LAUNCHER
    chmod +x "$HOME/.local/bin/nexus"
    
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  NEXUS installed successfully!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "Installation directory: $NEXUS_DIR"
    echo ""
    echo -e "${YELLOW}Next steps:${NC}"
    echo ""
    echo "  1. Add to your PATH (if not already):"
    echo "     export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
    echo "  2. Configure your API keys:"
    echo "     edit $NEXUS_DIR/apps/api/.env"
    echo ""
    echo "  3. Start NEXUS:"
    echo "     nexus start"
    echo ""
    echo "  Or run directly:"
    echo "     cd $NEXUS_DIR && pnpm dev"
    echo ""
}

# Run
detect_os
install_nexus
