#!/usr/bin/env python3

import torch
from diffusers import StableDiffusionPipeline
from safetensors.torch import load_file
import os
from PIL import Image
import requests

def setup_video_pipeline():
    """
    Set up the AI video generation pipeline
    """
    print("🎬 Setting up AI Video Generation Pipeline")
    
    # Check GPU availability
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")
    
    # Paths
    lora_path = "/home/trainer/output/sofia_lora.safetensors"
    output_dir = "/home/trainer/videos"
    
    try:
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Load the base pipeline
        print("Loading Stable Diffusion pipeline...")
        pipe = StableDiffusionPipeline.from_pretrained(
            "runwayml/stable-diffusion-v1-5",
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
            safety_checker=None,
            requires_safety_checker=False
        )
        pipe = pipe.to(device)
        
        # Load LoRA weights
        print("Loading Sofia LoRA model...")
        lora_weights = load_file(lora_path)
        pipe.load_lora_weights(lora_weights)
        
        # Test generation
        print("Generating test image...")
        prompt = "sofia woman, professional headshot, high quality"
        image = pipe(prompt, num_inference_steps=20, guidance_scale=7.5).images[0]
        
        # Save test image
        test_image_path = os.path.join(output_dir, "sofia_test.jpg")
        image.save(test_image_path)
        print(f"✅ Test image saved: {test_image_path}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def create_simple_video():
    """
    Create a simple video by generating multiple frames
    """
    print("🎥 Creating simple video...")
    
    prompts = [
        "sofia woman, smiling, professional headshot",
        "sofia woman, looking left, professional headshot", 
        "sofia woman, looking right, professional headshot",
        "sofia woman, neutral expression, professional headshot"
    ]
    
    try:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        pipe = StableDiffusionPipeline.from_pretrained(
            "runwayml/stable-diffusion-v1-5",
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
            safety_checker=None,
            requires_safety_checker=False
        )
        pipe = pipe.to(device)
        
        # Load LoRA
        lora_weights = load_file("/home/trainer/output/sofia_lora.safetensors")
        pipe.load_lora_weights(lora_weights)
        
        frames = []
        for i, prompt in enumerate(prompts):
            print(f"Generating frame {i+1}/4: {prompt}")
            image = pipe(prompt, num_inference_steps=15, guidance_scale=7.5).images[0]
            frames.append(image)
        
        # Save frames
        output_dir = "/home/trainer/videos"
        for i, frame in enumerate(frames):
            frame.save(f"{output_dir}/frame_{i:03d}.jpg")
        
        print("✅ Video frames generated successfully!")
        print("Use ffmpeg to combine: ffmpeg -r 2 -i frame_%03d.jpg -c:v libx264 sofia_video.mp4")
        
        return True
        
    except Exception as e:
        print(f"❌ Video creation error: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting AI Video Pipeline Setup")
    
    # Step 1: Setup pipeline
    if setup_video_pipeline():
        print("\n✅ Pipeline setup successful!")
        
        # Step 2: Create simple video
        if create_simple_video():
            print("\n🎉 Video pipeline fully operational!")
        else:
            print("\n⚠️ Video creation failed, but pipeline is ready")
    else:
        print("\n❌ Pipeline setup failed")
