#!/bin/bash

# Docker Cleanup Script for ABI Project
# Prevents Docker conflicts and stuck containers

set -e

echo "🧹 ABI Docker Cleanup Script"
echo "================================"

# Function to check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        echo "❌ Docker is not running. Please start Docker Desktop first."
        exit 1
    fi
}

# Function to stop ABI containers gracefully
stop_abi_containers() {
    echo "🛑 Stopping ABI containers..."
    
    # Try graceful shutdown first
    if docker-compose --profile dev ps -q > /dev/null 2>&1; then
        docker-compose --profile dev down --timeout 10 || true
    fi
    
    # Force stop any remaining ABI containers
    docker ps -a --filter "name=abi-" --format "{{.Names}}" | while read container; do
        if [ ! -z "$container" ]; then
            echo "  Stopping $container"
            docker stop "$container" > /dev/null 2>&1 || true
            docker rm "$container" > /dev/null 2>&1 || true
        fi
    done
}

# Function to clean up stuck containers on port 5432
cleanup_postgres_conflicts() {
    echo "🔍 Checking for PostgreSQL port conflicts..."
    
    # Find containers using port 5432
    conflicted_containers=$(docker ps -a --filter "publish=5432" --format "{{.Names}}" || true)
    
    if [ ! -z "$conflicted_containers" ]; then
        echo "⚠️  Found containers using port 5432:"
        echo "$conflicted_containers"
        echo "  Removing conflicted containers..."
        
        echo "$conflicted_containers" | while read container; do
            if [ ! -z "$container" ]; then
                docker stop "$container" > /dev/null 2>&1 || true
                docker rm "$container" > /dev/null 2>&1 || true
                echo "    Removed: $container"
            fi
        done
    else
        echo "✅ No PostgreSQL port conflicts found"
    fi
}

# Function to prune Docker system
prune_docker() {
    echo "🗑️  Pruning unused Docker resources..."
    docker system prune -f --volumes > /dev/null 2>&1 || true
    echo "✅ Docker cleanup complete"
}

# Main cleanup function
main() {
    check_docker
    stop_abi_containers
    cleanup_postgres_conflicts
    prune_docker
    
    echo ""
    echo "🎉 Cleanup complete! You can now run:"
    echo "   make dev-up    # Start development services"
    echo "   make           # Start ABI agent"
}

# Run cleanup if called directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi