#!/bin/bash

# Docker Setup Script for AI Influencer System
set -e

echo "🐳 AI Influencer System - Docker Setup"
echo "======================================"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first:"
    echo "   https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is available
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not available. Please install Docker Compose:"
    echo "   https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✅ Docker and Docker Compose are available"

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "✏️ Please edit .env file with your configuration"
fi

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p data/{loras,images,video_clips,final_videos,prompts}
mkdir -p logs

# Detect GPU support
echo "🔍 Checking for GPU support..."
if command -v nvidia-smi &> /dev/null && nvidia-smi &> /dev/null; then
    echo "🎮 NVIDIA GPU detected!"
    echo ""
    echo "You can use either:"
    echo "  1. CPU version: docker-compose up"
    echo "  2. GPU version: docker-compose --profile gpu up"
    echo ""
    echo "For GPU support, make sure you have nvidia-container-toolkit installed:"
    echo "  https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html"
    GPU_AVAILABLE=true
else
    echo "💻 No NVIDIA GPU detected, will use CPU version"
    GPU_AVAILABLE=false
fi

echo ""
echo "🐳 Docker setup options:"
echo "======================="
echo ""
echo "1. Build and run with Docker Compose (recommended):"
echo "   docker-compose up --build"
echo ""
echo "2. Build and run in background:"
echo "   docker-compose up -d --build"
echo ""

if [ "$GPU_AVAILABLE" = true ]; then
    echo "3. Build and run with GPU support:"
    echo "   docker-compose --profile gpu up --build"
    echo ""
fi

echo "4. Build Docker image only:"
echo "   docker build -t ai-influencer-system ."
echo ""
echo "5. Run built image:"
echo "   docker run -p 8000:8000 -v \$(pwd)/data:/app/data ai-influencer-system"
echo ""

# Ask user what they want to do
echo "What would you like to do?"
echo "1) Build and run with Docker Compose (CPU)"
if [ "$GPU_AVAILABLE" = true ]; then
    echo "2) Build and run with GPU support"
    echo "3) Just setup, don't run"
else
    echo "2) Just setup, don't run"
fi
echo ""

read -p "Enter your choice (1-3): " choice

case $choice in
    1)
        echo "🚀 Building and starting with Docker Compose (CPU)..."
        docker-compose up --build
        ;;
    2)
        if [ "$GPU_AVAILABLE" = true ]; then
            echo "🚀 Building and starting with GPU support..."
            docker-compose --profile gpu up --build
        else
            echo "✅ Setup complete! You can now run:"
            echo "   docker-compose up --build"
        fi
        ;;
    3)
        if [ "$GPU_AVAILABLE" = true ]; then
            echo "✅ Setup complete! You can now run:"
            echo "   docker-compose up --build              # CPU version"
            echo "   docker-compose --profile gpu up --build # GPU version"
        else
            echo "✅ Setup complete! You can now run:"
            echo "   docker-compose up --build"
        fi
        ;;
    *)
        echo "✅ Setup complete! Choose your run command above."
        ;;
esac

echo ""
echo "📖 Usage Tips:"
echo "=============="
echo "• Add your LoRA models to data/loras/"
echo "• Edit config/config.yaml for your trigger words"
echo "• Access API docs at: http://localhost:8000/docs"
echo "• View logs with: docker-compose logs -f"
echo "• Stop with: docker-compose down"
echo "• Clean up with: docker-compose down -v --rmi all"
