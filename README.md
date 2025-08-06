# AI Influencer System

A comprehensive system for generating consistent AI influencer content using LoRA models, Stable Diffusion, and Stable Video Diffusion.

## 🎯 Features

- **Consistent Character Generation**: Use LoRA models to maintain character consistency across all content
- **Image & Video Generation**: Generate both static images and animated videos
- **Content Pipeline**: High-level content creation from simple concepts
- **Batch Processing**: Generate multiple pieces of content efficiently
- **REST API**: Full-featured API for integration with other systems
- **Local & Cloud Storage**: Support for both local storage and S3
- **Mac M1/M2 Support**: Optimized for Apple Silicon (MPS) and NVIDIA GPUs

## 🏗️ Architecture

```
ai-influencer-system/
├── src/
│   ├── image_generation/    # Stable Diffusion + LoRA
│   ├── video_generation/    # Stable Video Diffusion
│   ├── orchestration/       # Content pipeline
│   ├── api/                # FastAPI web interface
│   └── utils/              # Configuration & storage
├── data/                   # Generated content storage
├── config/                 # Configuration files
└── scripts/               # Setup & utility scripts
```

## 🚀 Quick Start

### Option 1: Docker (Recommended)

```bash
# Clone or create the project
cd ai-influencer-system

# Setup and run with Docker
./scripts/docker_setup.sh

# Or manually:
docker-compose up --build

# With GPU support (if available):
docker-compose --profile gpu up --build
```

### Option 2: Local Installation

```bash
# Run setup script
./scripts/setup.sh

# Or manual setup:
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit configuration
nano .env
```

Set your device type:
- `DEVICE=mps` for Mac M1/M2
- `DEVICE=cuda` for NVIDIA GPU
- `DEVICE=cpu` for CPU only

### 3. Add LoRA Models

Place your trained LoRA models (`.safetensors` files) in the `data/loras/` directory.

### 4. Test the System

```bash
python scripts/test_system.py
```

### 5. Start the API Server

```bash
python -m src.api.main
```

Visit http://localhost:8000/docs for the interactive API documentation.

## 📖 Usage Examples

### Python API

```python
from src.orchestration.pipeline import content_pipeline
from src.image_generation.generator import image_generator

# Generate a single image
image_path = image_generator.generate_image(
    prompt="photo of sks woman, smiling, coffee shop background",
    lora_name="my_character.safetensors",
    save_image=True
)

# Create content from concept
result = content_pipeline.create_content_from_concept(
    concept="talking about morning coffee routine",
    lora_name="my_character.safetensors",
    num_videos=3
)

print(f"Generated content: {result['final_video']}")
```

### REST API

```bash
# Generate an image
curl -X POST "http://localhost:8000/generate/image" \\
     -H "Content-Type: application/json" \\
     -d '{
       "prompt": "photo of sks woman, professional headshot",
       "lora_name": "my_character.safetensors"
     }'

# Create content from concept
curl -X POST "http://localhost:8000/create/content" \\
     -H "Content-Type: application/json" \\
     -d '{
       "concept": "fitness motivation",
       "lora_name": "my_character.safetensors",
       "num_videos": 2
     }'
```

## 🎨 Training Your Own LoRA

While this system doesn't include LoRA training, you can train your own using tools like:

1. **[kohya_ss](https://github.com/kohya-ss/sd-scripts)**: Popular LoRA training toolkit
2. **[AUTOMATIC1111](https://github.com/AUTOMATIC1111/stable-diffusion-webui)**: With Dreambooth/LoRA extensions

### LoRA Training Tips

1. **Dataset Preparation**:
   - 15-25 high-quality images of your character
   - Various angles, expressions, and backgrounds
   - 512x512 or 768x768 resolution

2. **Trigger Word**:
   - Use a unique token like `sks woman` or `xyz person`
   - Update `config/config.yaml` with your trigger word

3. **Training Parameters**:
   - Learning rate: 1e-4 to 5e-4
   - Training steps: 1000-2000
   - Batch size: 1-2

## ⚙️ Configuration

### Main Config (`config/config.yaml`)

```yaml
# Update trigger word for your LoRA
lora:
  trigger_word: "sks woman"  # Change this!

# Device settings
models:
  stable_diffusion:
    device: "mps"  # cuda, mps, or cpu
```

### Environment Variables (`.env`)

```bash
# Device (overrides config.yaml)
DEVICE=mps

# AWS S3 (optional)
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
S3_BUCKET_NAME=your_bucket
```

## 🎬 Content Types

### Supported Concepts

The system includes built-in prompt variations for:

- **Coffee/Food**: Cafe scenes, cooking, food reviews
- **Fashion**: Outfit showcases, style tips
- **Fitness**: Workout content, wellness tips
- **Travel**: Adventure content, destination showcases
- **Lifestyle**: Daily routines, general content

### Custom Concepts

You can create content with any concept - the system will generate appropriate variations automatically.

## 🔧 Advanced Usage

### Batch Content Generation

```python
# Generate content for multiple concepts
concepts = ["morning routine", "workout tips", "coffee review"]
results = content_pipeline.generate_batch_content(
    concepts=concepts,
    lora_name="my_character.safetensors"
)
```

### Character Showcases

```python
# Create a personality showcase
showcase = content_pipeline.create_character_showcase(
    lora_name="my_character.safetensors",
    showcase_type="personality"  # or "fashion", "lifestyle"
)
```

### Video Parameters

```python
# Custom video generation
video_path = video_generator.generate_video_from_image(
    image="path/to/image.png",
    width=576,
    height=1024,  # Portrait for social media
    num_frames=25,
    fps=7,
    motion_bucket_id=127  # Higher = more motion
)
```

## 📊 Monitoring & Logging

- Logs are stored in `logs/` directory
- API logs: `logs/api.log`
- Set log level in `.env`: `LOG_LEVEL=INFO`

## 🐳 Docker Usage

### Docker Commands

```bash
# Quick setup and start
./scripts/docker_setup.sh

# Manual Docker Compose commands
docker-compose up --build              # CPU version
docker-compose --profile gpu up --build # GPU version
docker-compose up -d --build           # Run in background

# Management commands
./scripts/docker_manage.sh start        # Start system
./scripts/docker_manage.sh stop         # Stop system
./scripts/docker_manage.sh logs follow  # Follow logs
./scripts/docker_manage.sh shell        # Open container shell
./scripts/docker_manage.sh status       # Show status
```

### Docker Benefits

- **Consistent Environment**: Same setup across different machines
- **Easy GPU Support**: Automatic CUDA configuration
- **Isolated Dependencies**: No conflicts with host system
- **Production Ready**: Easy deployment and scaling

### Volume Mounts

- `./data` → `/app/data`: Persistent storage for LoRAs and generated content
- `./logs` → `/app/logs`: Log files
- `./config` → `/app/config`: Configuration files
- `./.env` → `/app/.env`: Environment variables

### GPU Support

For NVIDIA GPU support:

1. Install [nvidia-container-toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
2. Use the GPU profile: `docker-compose --profile gpu up --build`

## 🚨 Troubleshooting

### Common Issues

1. **CUDA Out of Memory**:
   ```python
   # Reduce batch size or image resolution in config.yaml
   image_generation:
     width: 512
     height: 512
   ```

2. **LoRA Not Loading**:
   - Ensure `.safetensors` files are in `data/loras/`
   - Check trigger word matches your LoRA training

3. **Slow Generation**:
   - Reduce `num_inference_steps` in config
   - Use smaller image/video dimensions
   - Enable GPU acceleration

4. **FFmpeg Errors**:
   ```bash
   # Install FFmpeg
   brew install ffmpeg  # macOS
   sudo apt install ffmpeg  # Ubuntu
   ```

### Performance Tips

- **Mac M1/M2**: Use `device: "mps"` in config
- **NVIDIA GPU**: Use `device: "cuda"` with appropriate PyTorch version
- **Memory Management**: Call cleanup methods between generations
- **Storage**: Use S3 for production deployments

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `python scripts/test_system.py`
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- [Stability AI](https://stability.ai/) for Stable Diffusion and Stable Video Diffusion
- [Hugging Face](https://huggingface.co/) for the diffusers library
- [kohya_ss](https://github.com/kohya-ss/sd-scripts) for LoRA training tools

## 📞 Support

- **Issues**: Use GitHub Issues for bug reports
- **Discussions**: Use GitHub Discussions for questions
- **Documentation**: Check `/docs` endpoint when API is running

---

**⚠️ Ethical Use**: This system is designed for creative and educational purposes. Please use responsibly and respect others' rights and privacy.
