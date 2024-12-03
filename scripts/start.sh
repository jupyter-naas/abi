#!/bin/bash

# Base URL
BASE_URL="http://localhost:8888"

# Save cursor position and clear screen
save_cursor() {
    echo -e "\033[s"  # Save cursor position
}

# Restore cursor position
restore_cursor() {
    echo -e "\033[u"  # Restore cursor position
}

# Function to display the header
show_header() {
    echo -e "\033[1;36m"  # Cyan color
    echo "
     █████╗ ██████╗ ██╗
    ██╔══██╗██╔══██╗██║
    ███████║██████╔╝██║
    ██╔══██║██╔══██╗██║
    ██║  ██║██████╔╝██║
    ╚═╝  ╚═╝╚═════╝ ╚═╝"
    echo -e "\033[0m"

    echo -e "\033[1;32m"  # Green color
    echo "    AI SYSTEM INITIALIZING..."
    echo -e "\033[0m"

    echo -e "\033[1;34m"  # Blue color
    echo "    📚 Documentation:"
    echo "    • Swagger UI: http://localhost:8888/docs"
    echo "    • ReDoc:     http://localhost:8888/redoc"
    echo -e "\033[0m"

    echo -e "\033[1;33m"  # Yellow color
    echo "    🔗 API Endpoints:"
    echo "    • Root:     http://localhost:8888"
    echo "    • Ontology: http://localhost:8888/ontology/structure"
    echo "    • Levels:   http://localhost:8888/ontology/ontologies/{level}"
    echo -e "\033[0m"

    echo -e "\033[1;35m"  # Purple color
    echo "    📋 Server Logs Below"
    echo "    ═══════════════════════════════════════════"
    echo -e "\033[0m"
}

# Clear screen
clear

# Show header and save cursor position
show_header
save_cursor

# Start uvicorn with cursor restoration
exec uvicorn api.main:app --host 0.0.0.0 --port 8888 --reload