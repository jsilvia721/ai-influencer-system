#!/usr/bin/env python3

import torch
from diffusers import StableDiffusionPipeline
import os
from PIL import Image

def test_basic_generation():
    """
    Test basic image generation without LoRA first
    """
    print("🎬 Testing Basic Video Pipeline")
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")
    
    try:
        # Create output directory
        output_dir = "/home/trainer/videos"
        os.makedirs(output_dir, exist_ok=True)
        
        # Load base pipeline
        print("Loading Stable Diffusion pipeline...")
        pipe = StableDiffusionPipeline.from_pretrained(
            "runwayml/stable-diffusion-v1-5",
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
            safety_checker=None,
            requires_safety_checker=False
        )
        pipe = pipe.to(device)
        
        # Test generation
        print("Generating test image...")
        prompt = "professional headshot of a woman, high quality, detailed"
        image = pipe(prompt, num_inference_steps=20, guidance_scale=7.5).images[0]
        
        # Save test image
        test_image_path = os.path.join(output_dir, "test_generation.jpg")
        image.save(test_image_path)
        print(f"✅ Test image saved: {test_image_path}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def create_video_frames():
    """
    Generate multiple frames for a simple video
    """
    print("🎥 Creating video frames...")
    
    prompts = [
        "professional headshot of a woman, smiling, high quality",
        "professional headshot of a woman, looking left, high quality", 
        "professional headshot of a woman, looking right, high quality",
        "professional headshot of a woman, neutral expression, high quality"
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
        
        output_dir = "/home/trainer/videos"
        
        for i, prompt in enumerate(prompts):
            print(f"Generating frame {i+1}/4: {prompt}")
            image = pipe(prompt, num_inference_steps=15, guidance_scale=7.5).images[0]
            image.save(f"{output_dir}/frame_{i:03d}.jpg")
        
        print("✅ Video frames generated successfully!")
        print("📹 To create video: ffmpeg -r 2 -i frame_%03d.jpg -c:v libx264 -pix_fmt yuv420p test_video.mp4")
        
        return True
        
    except Exception as e:
        print(f"❌ Video creation error: {e}")
        return False

def install_ffmpeg():
    """
    Install ffmpeg for video creation
    """
    print("📦 Installing ffmpeg...")
    try:
        os.system("sudo apt update && sudo apt install -y ffmpeg")
        print("✅ ffmpeg installed successfully")
        return True
    except Exception as e:
        print(f"❌ ffmpeg installation failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting Simple Video Pipeline Test")
    
    # Step 1: Test basic generation
    if test_basic_generation():
        print("\n✅ Basic generation test passed!")
        
        # Step 2: Create video frames
        if create_video_frames():
            print("\n🎉 Video frames created successfully!")
            
            # Step 3: Install ffmpeg and create video
            if install_ffmpeg():
                print("\n🎬 Creating final video...")
                os.system("cd /home/trainer/videos && ffmpeg -r 2 -i frame_%03d.jpg -c:v libx264 -pix_fmt yuv420p basic_video.mp4")
                print("✅ Video created: /home/trainer/videos/basic_video.mp4")
            else:
                print("\n⚠️ Video frames ready, but ffmpeg installation failed")
        else:
            print("\n❌ Video frame creation failed")
    else:
        print("\n❌ Basic generation test failed")
