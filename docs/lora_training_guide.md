# LoRA Training Guide for AI Influencer System

## 📋 Prerequisites

- NVIDIA GPU with at least 8GB VRAM (12GB+ recommended)
- Python 3.10+
- About 2-4 hours for training
- 15-25 high-quality images of your subject

## 🛠️ Method 1: Using kohya_ss (Recommended)

### Installation

```bash
# Clone kohya_ss
git clone https://github.com/kohya-ss/sd-scripts.git
cd sd-scripts

# Install dependencies
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
pip install -r requirements.txt
pip install -U -I --no-deps https://github.com/C43H66N12O12S2/stable-diffusion-webui/releases/download/f/xformers-0.0.20+814314d.d20230406-cp310-cp310-win_amd64.whl

# Install accelerate and configure
accelerate config
```

### Dataset Preparation

1. **Create folder structure:**
```
training_data/
├── 10_sks woman/           # 10 = repeat count, "sks woman" = trigger phrase
│   ├── image1.jpg
│   ├── image2.jpg
│   └── ...
└── reg/                    # Regularization images (optional)
    └── 1_woman/
        ├── reg1.jpg
        └── ...
```

2. **Image requirements:**
   - 512x512 or 768x768 resolution
   - JPG or PNG format
   - High quality, well-lit
   - Diverse poses and expressions

### Training Script

```bash
accelerate launch --num_cpu_threads_per_process=2 train_network.py \
    --enable_bucket \
    --pretrained_model_name_or_path="runwayml/stable-diffusion-v1-5" \
    --train_data_dir="./training_data" \
    --resolution=512,512 \
    --output_dir="./output" \
    --logging_dir="./logs" \
    --network_alpha=32 \
    --save_model_as=safetensors \
    --network_module=networks.lora \
    --text_encoder_lr=5e-5 \
    --unet_lr=1e-4 \
    --network_dim=32 \
    --output_name="my_character_lora" \
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
```

## 🖥️ Method 2: Using AUTOMATIC1111 WebUI

### Installation

```bash
# Clone AUTOMATIC1111
git clone https://github.com/AUTOMATIC1111/stable-diffusion-webui.git
cd stable-diffusion-webui

# Install (will auto-install dependencies)
./webui.sh  # Linux/Mac
# or webui-user.bat  # Windows
```

### Training Steps

1. **Install Dreambooth/LoRA extension**
2. **Go to "Train" tab**
3. **Select "LoRA" training type**
4. **Configure settings:**
   - Model: stable-diffusion-v1-5
   - Instance prompt: "sks woman"
   - Class prompt: "woman" (for regularization)
   - Learning rate: 1e-4
   - Training steps: 1000-2000
   - Batch size: 1

## 🎯 Method 3: Online Services (Easiest)

### Replicate.com
- Upload 10-20 images
- Pay ~$5-10 per model
- Fully automated process
- Good quality results

### RunDiffusion
- Web-based LoRA training
- No local GPU required
- Professional quality

### Civitai
- Community platform
- Browse existing LoRAs
- Upload and share your own

## 📝 Training Parameters Explained

| Parameter | Recommended | Description |
|-----------|-------------|-------------|
| Learning Rate | 1e-4 to 5e-4 | How fast the model learns |
| Training Steps | 1000-2000 | Number of training iterations |
| Network Dim | 32-128 | LoRA complexity (higher = more detailed) |
| Network Alpha | 16-32 | Training stability |
| Batch Size | 1-2 | Images processed together |
| Trigger Word | "sks woman" | Unique identifier for your character |

## 🔍 Quality Tips

### Good Training Images:
✅ Clear, high resolution  
✅ Good lighting  
✅ Various angles and expressions  
✅ Consistent subject  
✅ Minimal background distractions  

### Avoid:
❌ Blurry or low quality images  
❌ Heavy filters or editing  
❌ Multiple people in frame  
❌ Extreme poses or expressions  
❌ Copyrighted characters  

## 🧪 Testing Your LoRA

Once trained, test with prompts like:
- "photo of sks woman, smiling, professional headshot"
- "sks woman in casual clothes, coffee shop background"
- "portrait of sks woman, studio lighting"

## 🔧 Troubleshooting

### Common Issues:

1. **Overfitting**: Model only generates training images exactly
   - Solution: Reduce training steps or learning rate

2. **Underfitting**: Model doesn't capture the character well
   - Solution: Increase training steps or improve dataset

3. **Bias**: Model always generates same pose/expression
   - Solution: Add more diverse training images

4. **Artifacts**: Strange distortions in generated images
   - Solution: Lower learning rate or network dimension

## 💾 Using Your LoRA

1. **Save the `.safetensors` file** to your `data/loras/` directory
2. **Update `config/config.yaml`** with your trigger word
3. **Test in the API** with your trigger phrase

Example API call:
```bash
curl -X POST "http://localhost:8000/generate/image" \
     -H "Content-Type: application/json" \
     -d '{
       "prompt": "photo of sks woman, smiling, coffee shop background",
       "lora_name": "my_character_lora.safetensors"
     }'
```

## 📚 Additional Resources

- [Civitai LoRA Guide](https://civitai.com/articles/143/complete-lora-guide)
- [kohya_ss Documentation](https://github.com/kohya-ss/sd-scripts)
- [AUTOMATIC1111 Wiki](https://github.com/AUTOMATIC1111/stable-diffusion-webui/wiki)
- [LoRA Training Discord Communities](https://discord.gg/stablediffusion)

## ⚖️ Legal and Ethical Considerations

- **Only use images you have rights to**
- **Respect privacy and consent**
- **Don't create LoRAs of real people without permission**
- **Follow platform terms of service**
- **Consider the impact of synthetic media**
