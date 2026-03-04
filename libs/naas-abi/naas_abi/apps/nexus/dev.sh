#!/bin/bash
# Development server wrapper with proper signal handling
# Ensures all child processes are killed on Ctrl+C

set -e

# Colors
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}Starting NEXUS development servers...${NC}"

# Trap SIGINT (Ctrl+C) and kill all child processes
cleanup() {
    echo -e "\n${YELLOW}Shutting down servers...${NC}"
    # Kill all processes in the process group
    pkill -P $$ || true
    # Also kill by port (backup)
    lsof -ti:3000 | xargs kill -9 2>/dev/null || true
    lsof -ti:8000 | xargs kill -9 2>/dev/null || true
    echo -e "${GREEN}✓ Servers stopped${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Run turbo in foreground
pnpm dev

# Should never reach here, but just in case
cleanup
