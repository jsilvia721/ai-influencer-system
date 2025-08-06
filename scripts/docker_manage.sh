#!/bin/bash

# Docker Management Script for AI Influencer System
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🐳 AI Influencer System - Docker Management${NC}"
echo "=============================================="

# Function to show usage
show_usage() {
    echo -e "\n${YELLOW}Usage:${NC}"
    echo "  $0 [command] [options]"
    echo ""
    echo -e "${YELLOW}Commands:${NC}"
    echo "  start [cpu|gpu]    - Start the system (default: cpu)"
    echo "  stop               - Stop the system"
    echo "  restart [cpu|gpu]  - Restart the system"
    echo "  logs [follow]      - Show logs (add 'follow' to tail)"
    echo "  status             - Show container status"
    echo "  clean              - Clean up containers and images"
    echo "  deep-clean         - Clean everything including volumes"
    echo "  shell              - Open shell in running container"
    echo "  build [cpu|gpu]    - Build the Docker image"
    echo "  test               - Run tests in container"
    echo ""
    echo -e "${YELLOW}Examples:${NC}"
    echo "  $0 start           # Start with CPU"
    echo "  $0 start gpu       # Start with GPU support"
    echo "  $0 logs follow     # Follow logs in real-time"
    echo "  $0 shell           # Open bash shell in container"
}

# Function to check if Docker is running
check_docker() {
    if ! docker info >/dev/null 2>&1; then
        echo -e "${RED}❌ Docker is not running. Please start Docker first.${NC}"
        exit 1
    fi
}

# Function to detect GPU availability
check_gpu() {
    if command -v nvidia-smi &> /dev/null && nvidia-smi &> /dev/null; then
        return 0  # GPU available
    else
        return 1  # No GPU
    fi
}

# Function to start the system
start_system() {
    local mode=${1:-cpu}
    
    echo -e "${GREEN}🚀 Starting AI Influencer System (${mode} mode)...${NC}"
    
    if [ "$mode" = "gpu" ]; then
        if ! check_gpu; then
            echo -e "${YELLOW}⚠️ No GPU detected, falling back to CPU mode${NC}"
            mode="cpu"
        fi
    fi
    
    # Create .env if it doesn't exist
    if [ ! -f ".env" ]; then
        echo -e "${YELLOW}📝 Creating .env file...${NC}"
        cp .env.example .env
    fi
    
    # Start appropriate service
    if [ "$mode" = "gpu" ]; then
        docker-compose --profile gpu up -d --build
    else
        docker-compose up -d --build
    fi
    
    echo -e "${GREEN}✅ System started successfully!${NC}"
    echo -e "API available at: ${BLUE}http://localhost:8000${NC}"
    echo -e "API docs at: ${BLUE}http://localhost:8000/docs${NC}"
}

# Function to stop the system
stop_system() {
    echo -e "${YELLOW}🛑 Stopping AI Influencer System...${NC}"
    docker-compose down
    echo -e "${GREEN}✅ System stopped${NC}"
}

# Function to restart the system
restart_system() {
    local mode=${1:-cpu}
    echo -e "${YELLOW}🔄 Restarting AI Influencer System...${NC}"
    stop_system
    sleep 2
    start_system "$mode"
}

# Function to show logs
show_logs() {
    local follow=${1:-}
    
    if [ "$follow" = "follow" ] || [ "$follow" = "-f" ]; then
        echo -e "${BLUE}📋 Following logs (Ctrl+C to stop)...${NC}"
        docker-compose logs -f
    else
        echo -e "${BLUE}📋 Showing recent logs...${NC}"
        docker-compose logs --tail=50
    fi
}

# Function to show status
show_status() {
    echo -e "${BLUE}📊 Container Status:${NC}"
    docker-compose ps
    
    echo -e "\n${BLUE}💾 Image Information:${NC}"
    docker images | grep -E "(ai-influencer|REPOSITORY)"
    
    echo -e "\n${BLUE}🔗 Network Information:${NC}"
    docker network ls | grep -E "(ai-influencer|NETWORK)"
}

# Function to clean up
clean_system() {
    echo -e "${YELLOW}🧹 Cleaning up containers and images...${NC}"
    docker-compose down --rmi local
    echo -e "${GREEN}✅ Cleanup complete${NC}"
}

# Function to deep clean
deep_clean() {
    echo -e "${RED}🗑️ Deep cleaning (this will remove all data volumes!)${NC}"
    read -p "Are you sure? This will delete all generated content. (y/N): " confirm
    
    if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
        docker-compose down -v --rmi all
        docker system prune -f
        echo -e "${GREEN}✅ Deep cleanup complete${NC}"
    else
        echo -e "${YELLOW}🚫 Deep clean cancelled${NC}"
    fi
}

# Function to open shell
open_shell() {
    local container_name=$(docker-compose ps -q ai-influencer 2>/dev/null || docker-compose ps -q ai-influencer-gpu 2>/dev/null)
    
    if [ -z "$container_name" ]; then
        echo -e "${RED}❌ No running container found. Start the system first.${NC}"
        exit 1
    fi
    
    echo -e "${BLUE}🐚 Opening shell in container...${NC}"
    docker exec -it "$container_name" /bin/bash
}

# Function to build image
build_image() {
    local mode=${1:-cpu}
    
    echo -e "${GREEN}🔨 Building Docker image (${mode} mode)...${NC}"
    
    if [ "$mode" = "gpu" ]; then
        docker build -f Dockerfile.gpu -t ai-influencer-system:gpu .
    else
        docker build -t ai-influencer-system:cpu .
    fi
    
    echo -e "${GREEN}✅ Build complete${NC}"
}

# Function to run tests
run_tests() {
    echo -e "${BLUE}🧪 Running tests in container...${NC}"
    
    # Build test image
    docker build -t ai-influencer-test .
    
    # Run tests
    docker run --rm \
        -v "$(pwd)/data:/app/data" \
        ai-influencer-test \
        python scripts/test_system.py
}

# Main script logic
check_docker

case "${1:-}" in
    start)
        start_system "${2:-cpu}"
        ;;
    stop)
        stop_system
        ;;
    restart)
        restart_system "${2:-cpu}"
        ;;
    logs)
        show_logs "${2:-}"
        ;;
    status)
        show_status
        ;;
    clean)
        clean_system
        ;;
    deep-clean)
        deep_clean
        ;;
    shell)
        open_shell
        ;;
    build)
        build_image "${2:-cpu}"
        ;;
    test)
        run_tests
        ;;
    help|--help|-h)
        show_usage
        ;;
    "")
        echo -e "${YELLOW}No command specified.${NC}"
        show_usage
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        show_usage
        exit 1
        ;;
esac
