#!/usr/bin/env python3
"""
Dataset preparation script for LoRA training.

This script helps prepare your images for LoRA training by:
1. Resizing images to proper dimensions
2. Creating the correct folder structure
3. Generating basic captions
4. Validating image quality
"""

import os
import sys
from pathlib import Path
from PIL import Image, ImageEnhance
import argparse
from typing import List, Tuple
import shutil

def resize_image(image_path: Path, target_size: int = 512) -> Image.Image:
    """Resize image to square format while maintaining aspect ratio."""
    with Image.open(image_path) as img:
        # Convert to RGB if necessary
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Calculate dimensions to maintain aspect ratio
        width, height = img.size
        
        if width == height:
            # Already square
            return img.resize((target_size, target_size), Image.Resampling.LANCZOS)
        
        # Make square by cropping to center
        size = min(width, height)
        left = (width - size) // 2
        top = (height - size) // 2
        right = left + size
        bottom = top + size
        
        img_cropped = img.crop((left, top, right, bottom))
        return img_cropped.resize((target_size, target_size), Image.Resampling.LANCZOS)

def enhance_image(img: Image.Image) -> Image.Image:
    """Apply basic enhancements to improve image quality."""
    # Slightly increase sharpness
    enhancer = ImageEnhance.Sharpness(img)
    img = enhancer.enhance(1.1)
    
    # Slightly increase contrast
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.05)
    
    return img

def validate_image(image_path: Path) -> Tuple[bool, str]:
    """Validate if image is suitable for training."""
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            
            # Check minimum size
            if min(width, height) < 256:
                return False, f"Image too small: {width}x{height} (minimum 256px)"
            
            # Check if image is not too blurry (basic check)
            if img.mode not in ['RGB', 'RGBA', 'L']:
                return False, f"Unsupported image mode: {img.mode}"
            
            # Check file size (basic quality indicator)
            file_size = image_path.stat().st_size
            if file_size < 10000:  # Less than 10KB is probably too low quality
                return False, f"File too small: {file_size} bytes"
            
            return True, "OK"
    
    except Exception as e:
        return False, f"Error reading image: {e}"

def create_dataset_structure(
    input_dir: Path,
    output_dir: Path,
    trigger_word: str = "sks woman",
    repeat_count: int = 10,
    target_size: int = 512,
    enhance: bool = True
):
    """Create the dataset structure for kohya_ss training."""
    
    # Create output directory
    training_dir = output_dir / f"{repeat_count}_{trigger_word}"
    training_dir.mkdir(parents=True, exist_ok=True)
    
    # Find all image files
    image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
    image_files = []
    
    for ext in image_extensions:
        image_files.extend(input_dir.glob(f"*{ext}"))
        image_files.extend(input_dir.glob(f"*{ext.upper()}"))
    
    if not image_files:
        print(f"❌ No images found in {input_dir}")
        return False
    
    print(f"📁 Found {len(image_files)} images")
    
    processed_count = 0
    skipped_count = 0
    
    for i, image_path in enumerate(image_files):
        print(f"📸 Processing {image_path.name} ({i+1}/{len(image_files)})")
        
        # Validate image
        is_valid, message = validate_image(image_path)
        if not is_valid:
            print(f"  ⚠️ Skipping: {message}")
            skipped_count += 1
            continue
        
        try:
            # Resize and enhance image
            img = resize_image(image_path, target_size)
            
            if enhance:
                img = enhance_image(img)
            
            # Save processed image
            output_filename = f"image_{i+1:03d}.jpg"
            output_path = training_dir / output_filename
            img.save(output_path, "JPEG", quality=95)
            
            # Create basic caption file
            caption_path = training_dir / f"image_{i+1:03d}.txt"
            with open(caption_path, 'w') as f:
                f.write(f"{trigger_word}, high quality photo")
            
            processed_count += 1
            print(f"  ✅ Saved as {output_filename}")
            
        except Exception as e:
            print(f"  ❌ Error processing: {e}")
            skipped_count += 1
    
    print(f"\n🎉 Dataset preparation complete!")
    print(f"  ✅ Processed: {processed_count} images")
    print(f"  ⚠️ Skipped: {skipped_count} images")
    print(f"  📁 Output: {training_dir}")
    
    return processed_count > 0

def create_config_file(
    output_dir: Path,
    trigger_word: str,
    learning_rate: float = 1e-4,
    max_train_steps: int = 1600,
    network_dim: int = 32
):
    """Create a kohya_ss configuration file."""
    
    config_content = f"""# LoRA Training Configuration
# Generated by AI Influencer System

[model]
pretrained_model_name_or_path = "runwayml/stable-diffusion-v1-5"
v2 = false
v_parameterization = false

[training]
output_dir = "./output"
save_model_as = "safetensors"
output_name = "my_character_lora"

# Learning parameters
learning_rate = {learning_rate}
lr_scheduler = "cosine"
lr_warmup_steps = 0
max_train_steps = {max_train_steps}
train_batch_size = 1

# Network parameters
network_module = "networks.lora"
network_dim = {network_dim}
network_alpha = 32

# Data parameters
train_data_dir = "{output_dir.absolute()}"
resolution = 512,512
enable_bucket = true
bucket_reso_steps = 64
bucket_no_upscale = true

# Optimization
mixed_precision = "fp16"
save_precision = "fp16"
optimizer_type = "AdamW8bit"
cache_latents = true
xformers = true

# Saving
save_every_n_epochs = 200
save_last_n_epochs = 5

# Instance settings
instance_prompt = "{trigger_word}"
class_prompt = "woman"  # Regularization class
"""
    
    config_path = output_dir / "training_config.toml"
    with open(config_path, 'w') as f:
        f.write(config_content)
    
    print(f"📝 Created config file: {config_path}")

def main():
    parser = argparse.ArgumentParser(
        description="Prepare images for LoRA training",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python prepare_dataset.py photos/ training_data/
  python prepare_dataset.py photos/ training_data/ --trigger "xyz person" --size 768
  python prepare_dataset.py photos/ training_data/ --no-enhance --repeat 15
        """
    )
    
    parser.add_argument("input_dir", type=Path, help="Directory containing input images")
    parser.add_argument("output_dir", type=Path, help="Output directory for training data")
    parser.add_argument("--trigger", default="sks woman", help="Trigger word for the LoRA (default: 'sks woman')")
    parser.add_argument("--repeat", type=int, default=10, help="Repeat count for training (default: 10)")
    parser.add_argument("--size", type=int, default=512, help="Target image size (default: 512)")
    parser.add_argument("--no-enhance", action="store_true", help="Skip image enhancement")
    parser.add_argument("--config", action="store_true", help="Generate training config file")
    
    args = parser.parse_args()
    
    # Validate input directory
    if not args.input_dir.exists():
        print(f"❌ Input directory not found: {args.input_dir}")
        sys.exit(1)
    
    if not args.input_dir.is_dir():
        print(f"❌ Input path is not a directory: {args.input_dir}")
        sys.exit(1)
    
    print(f"🚀 Preparing LoRA training dataset")
    print(f"  📂 Input: {args.input_dir}")
    print(f"  📂 Output: {args.output_dir}")
    print(f"  🎯 Trigger: '{args.trigger}'")
    print(f"  🔢 Repeat: {args.repeat}")
    print(f"  📏 Size: {args.size}x{args.size}")
    print(f"  ✨ Enhance: {not args.no_enhance}")
    print()
    
    # Create dataset
    success = create_dataset_structure(
        args.input_dir,
        args.output_dir,
        args.trigger,
        args.repeat,
        args.size,
        not args.no_enhance
    )
    
    if not success:
        print("❌ Dataset preparation failed")
        sys.exit(1)
    
    # Create config file if requested
    if args.config:
        create_config_file(args.output_dir, args.trigger)
    
    print(f"\n📖 Next steps:")
    print(f"1. Review the processed images in {args.output_dir}")
    print(f"2. Install kohya_ss or use AUTOMATIC1111 for training")
    print(f"3. Use trigger word '{args.trigger}' in your prompts")
    print(f"4. Train for ~1000-2000 steps with learning rate 1e-4")
    print(f"5. Place the resulting .safetensors file in data/loras/")

if __name__ == "__main__":
    main()
