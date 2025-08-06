#!/bin/bash

# AI Influencer System Setup Script
set -e

echo "🚀 Setting up AI Influencer System..."

# Check if Python 3.8+ is installed
python_version=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1-2)
required_version="3.8"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Python 3.8+ is required. Found: $python_version"
    exit 1
fi

echo "✅ Python version: $python_version"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️ Upgrading pip..."
pip install --upgrade pip

# Install PyTorch first (with appropriate CUDA support)
echo "🔥 Installing PyTorch..."
if command -v nvidia-smi &> /dev/null; then
    echo "🎮 NVIDIA GPU detected, installing CUDA version..."
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
else
    echo "💻 No NVIDIA GPU detected, installing CPU/MPS version..."
    pip install torch torchvision torchaudio
fi

# Install requirements
echo "📚 Installing Python dependencies..."
pip install -r requirements.txt

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p data/{loras,images,video_clips,final_videos,prompts}
mkdir -p logs

# Copy environment file
if [ ! -f ".env" ]; then
    echo "⚙️ Creating environment configuration..."
    cp .env.example .env
    echo "✏️ Please edit .env file with your configuration"
fi

# Set up logging directory
mkdir -p logs

# Check for FFmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo "⚠️ FFmpeg not found. Please install it:"
    echo "  macOS: brew install ffmpeg"
    echo "  Ubuntu: sudo apt install ffmpeg"
    echo "  Arch: sudo pacman -S ffmpeg"
fi

# Download sample LoRA (optional)
echo "🎭 Would you like to download a sample LoRA model? (y/n)"
read -r download_sample
if [ "$download_sample" = "y" ] || [ "$download_sample" = "Y" ]; then
    echo "📥 This would download a sample LoRA - implement this based on your needs"
    # wget -P data/loras/ https://your-sample-lora-url.safetensors
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "🎯 Next steps:"
echo "1. Edit .env file with your configuration"
echo "2. Place your LoRA models in data/loras/"
echo "3. Update config/config.yaml as needed"
echo "4. Run: python -m src.api.main to start the API server"
echo "5. Or use: python scripts/test_system.py to test the system"
echo ""
echo "📖 Documentation: Check README.md for usage examples"
echo "🌐 API docs will be available at: http://localhost:8000/docs"
