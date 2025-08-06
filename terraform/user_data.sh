#!/bin/bash

# User data script for AI training instance setup
# This script runs on instance launch to install dependencies and set up training environment

set -e  # Exit on any error

# Log everything to a file
exec > >(tee /var/log/user-data.log) 2>&1

echo "Starting AI training instance setup..."
echo "S3 Bucket: ${s3_bucket}"
echo "Project: ${project_name}"

# Update system
apt-get update
apt-get upgrade -y

# Install essential packages
apt-get install -y \
    wget \
    curl \
    git \
    unzip \
    htop \
    tmux \
    awscli \
    python3-pip \
    python3-venv

# Install NVIDIA drivers and CUDA (if not already in AMI)
# The Deep Learning AMI should already have these, but let's ensure they're working
nvidia-smi || {
    echo "NVIDIA drivers not found, installing..."
    # This would typically be handled by the Deep Learning AMI
}

# Create training user
useradd -m -s /bin/bash trainer
usermod -aG sudo trainer

# Set up directories
mkdir -p /home/trainer/training
mkdir -p /home/trainer/models
mkdir -p /home/trainer/data
chown -R trainer:trainer /home/trainer/

# Switch to trainer user for the rest of setup
sudo -u trainer bash << 'EOF'
cd /home/trainer

# Set up Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install PyTorch with CUDA support
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Clone and set up kohya_ss
git clone https://github.com/kohya-ss/sd-scripts.git training/kohya_ss
cd training/kohya_ss

# Install kohya_ss dependencies
pip install -r requirements.txt
pip install accelerate
pip install xformers

# Install additional useful packages
pip install \
    jupyter \
    tensorboard \
    boto3 \
    matplotlib \
    pillow

# Configure accelerate for single GPU training
accelerate config default

# Create training script
cat > /home/trainer/training/train_lora.sh << 'TRAIN_EOF'
#!/bin/bash

# LoRA Training Script for AWS
set -e

# Configuration
S3_BUCKET="${s3_bucket}"
MODEL_DIR="/home/trainer/models"
DATA_DIR="/home/trainer/data"
OUTPUT_DIR="/home/trainer/output"
KOHYA_DIR="/home/trainer/training/kohya_ss"

# Create directories
mkdir -p "$MODEL_DIR" "$DATA_DIR" "$OUTPUT_DIR"

# Download training data from S3
echo "Downloading training data from S3..."
aws s3 sync "s3://$S3_BUCKET/training_data/" "$DATA_DIR/"

# Download base model if needed
if [ ! -f "$MODEL_DIR/model.safetensors" ]; then
    echo "Downloading base model..."
    # You can add logic here to download your preferred base model
    # or use Hugging Face hub
fi

# Run training
echo "Starting LoRA training..."
cd "$KOHYA_DIR"

source /home/trainer/venv/bin/activate

# Start tensorboard in background
tensorboard --logdir="$OUTPUT_DIR/logs" --host=0.0.0.0 --port=6006 &

# Run training with optimized parameters for cost efficiency
accelerate launch --num_cpu_threads_per_process=2 train_network.py \
    --enable_bucket \
    --pretrained_model_name_or_path="runwayml/stable-diffusion-v1-5" \
    --train_data_dir="$DATA_DIR" \
    --resolution=512,512 \
    --output_dir="$OUTPUT_DIR" \
    --logging_dir="$OUTPUT_DIR/logs" \
    --network_alpha=32 \
    --save_model_as=safetensors \
    --network_module=networks.lora \
    --text_encoder_lr=5e-5 \
    --unet_lr=1e-4 \
    --network_dim=32 \
    --output_name="sofia_lora" \
    --lr_scheduler_num_cycles=1 \
    --no_half_vae \
    --learning_rate=1e-4 \
    --lr_scheduler="cosine" \
    --lr_warmup_steps=0 \
    --train_batch_size=1 \
    --max_train_steps=1600 \
    --save_every_n_epochs=200 \
    --mixed_precision="fp16" \
    --save_precision="fp16" \
    --cache_latents \
    --optimizer_type="AdamW8bit" \
    --max_data_loader_n_workers=0 \
    --bucket_reso_steps=64 \
    --xformers \
    --bucket_no_upscale

echo "Training completed!"

# Upload results to S3
echo "Uploading results to S3..."
aws s3 sync "$OUTPUT_DIR/" "s3://$S3_BUCKET/output/"

# Upload logs
aws s3 sync "$OUTPUT_DIR/logs/" "s3://$S3_BUCKET/logs/"

echo "Upload completed!"

# Optional: Shutdown instance after training (cost optimization)
# Uncomment the line below if you want automatic shutdown
# sudo shutdown -h +5  # Shutdown in 5 minutes
TRAIN_EOF

chmod +x /home/trainer/training/train_lora.sh

# Create monitoring script
cat > /home/trainer/training/monitor.sh << 'MONITOR_EOF'
#!/bin/bash

# Simple monitoring script
while true; do
    echo "=== $(date) ==="
    echo "GPU Status:"
    nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv
    echo "System Status:"
    free -h
    df -h /
    echo "Training Process:"
    pgrep -f "train_network.py" && echo "Training running" || echo "No training process found"
    echo "===================="
    sleep 60
done
MONITOR_EOF

chmod +x /home/trainer/training/monitor.sh

# Create Jupyter config for remote access
mkdir -p /home/trainer/.jupyter
cat > /home/trainer/.jupyter/jupyter_notebook_config.py << 'JUPYTER_EOF'
c.NotebookApp.ip = '0.0.0.0'
c.NotebookApp.port = 8888
c.NotebookApp.open_browser = False
c.NotebookApp.token = 'training-token'  # Change this for security
c.NotebookApp.allow_root = False
JUPYTER_EOF

EOF

# Set up systemd service for easy training management
cat > /etc/systemd/system/ai-training.service << 'SERVICE_EOF'
[Unit]
Description=AI LoRA Training Service
After=network.target

[Service]
Type=simple
User=trainer
WorkingDirectory=/home/trainer/training
ExecStart=/home/trainer/training/train_lora.sh
Restart=no
Environment=PATH=/home/trainer/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

[Install]
WantedBy=multi-user.target
SERVICE_EOF

systemctl daemon-reload
systemctl enable ai-training

# Create a simple startup script that can be triggered via user data or SSH
cat > /home/trainer/start_training.sh << 'START_EOF'
#!/bin/bash
echo "Starting AI training session..."
echo "You can monitor with: sudo systemctl status ai-training"
echo "View logs with: sudo journalctl -u ai-training -f"
echo "Or run directly: /home/trainer/training/train_lora.sh"

# Start monitoring in background
/home/trainer/training/monitor.sh > /home/trainer/monitoring.log 2>&1 &

echo "Setup complete! Training environment is ready."
echo "Instance IP: $(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)"
echo "Access Jupyter at: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8888"
echo "Access TensorBoard at: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):6006"
START_EOF

chmod +x /home/trainer/start_training.sh
chown trainer:trainer /home/trainer/start_training.sh

echo "User data script completed successfully!"
echo "Instance is ready for AI training!"
