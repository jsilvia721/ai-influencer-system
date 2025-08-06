#!/usr/bin/env python3
"""
Memory-Optimized AI Video Generator Test
Uses smaller models and optimized settings for Tesla T4
"""

import sys
import os
import torch
import numpy as np
from PIL import Image, ImageDraw
import logging
from datetime import datetime

# Import diffusion libraries
from diffusers import StableVideoDiffusionPipeline
from diffusers.utils import load_image, export_to_video

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_simple_test_image():
    """Create a simple test image optimized for video generation"""
    # Create a smaller, simpler image to reduce memory usage
    width, height = 512, 320  # Smaller resolution
    
    # Create base image
    img = Image.new("RGB", (width, height), (40, 50, 70))
    draw = ImageDraw.Draw(img)
    
    # Simple gradient background
    for y in range(height):
        color_val = int(40 + (y / height) * 50)
        draw.line([(0, y), (width, y)], fill=(color_val, color_val + 10, color_val + 20))
    
    # Simple face-like shape
    center_x, center_y = width // 2, height // 2
    
    # Head
    head_size = 80
    draw.ellipse([
        center_x - head_size, center_y - head_size,
        center_x + head_size, center_y + head_size
    ], fill=(200, 170, 150))
    
    # Eyes
    eye_size = 8
    draw.ellipse([center_x - 25, center_y - 20, center_x - 25 + eye_size, center_y - 20 + eye_size], fill=(0, 0, 0))
    draw.ellipse([center_x + 25, center_y - 20, center_x + 25 + eye_size, center_y - 20 + eye_size], fill=(0, 0, 0))
    
    # Mouth
    draw.ellipse([center_x - 15, center_y + 20, center_x + 15, center_y + 30], fill=(150, 100, 100))
    
    # Save the test image
    test_image_path = "simple_test.jpg"
    img.save(test_image_path, "JPEG", quality=90)
    logger.info(f"Created simple test image: {test_image_path}")
    
    return test_image_path

def test_simple_video_generation():
    """Test video generation with minimal memory usage"""
    try:
        logger.info("Starting memory-optimized video generation test...")
        
        # Create simple test image
        test_image = create_simple_test_image()
        
        # Initialize with memory optimizations
        logger.info("Loading Stable Video Diffusion with memory optimizations...")
        
        # Use the standard SVD model (not XT to save memory)
        pipeline = StableVideoDiffusionPipeline.from_pretrained(
            "stabilityai/stable-video-diffusion-img2vid",  # Standard model, not XT
            torch_dtype=torch.float16,
            variant="fp16"
        )
        
        # Memory optimizations
        pipeline.to("cuda")
        pipeline.enable_model_cpu_offload()
        pipeline.enable_vae_slicing()
        if hasattr(pipeline, "enable_vae_tiling"):
            pipeline.enable_vae_tiling()
        
        logger.info("Pipeline loaded with memory optimizations")
        
        # Load and preprocess image
        image = load_image(test_image)
        image = image.resize((512, 320))  # Smaller size for memory efficiency
        
        # Generate video with conservative settings
        logger.info("Generating video with conservative settings...")
        
        with torch.no_grad():
            frames = pipeline(
                image,
                decode_chunk_size=2,      # Very small chunks
                num_frames=14,            # Fewer frames (standard SVD max)
                motion_bucket_id=100,     # Lower motion
                noise_aug_strength=0.05,  # Less noise
                num_inference_steps=15,   # Fewer steps
            ).frames[0]
        
        # Export video
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"test_video_{timestamp}.mp4"
        
        logger.info(f"Exporting video to {output_path}")
        export_to_video(frames, output_path, fps=6)
        
        # Check result
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path) / (1024 * 1024)
            logger.info(f"✅ Video generated successfully!")
            logger.info(f"File: {output_path}")
            logger.info(f"Size: {file_size:.2f} MB")
            logger.info(f"Frames: {len(frames)}")
            
            return output_path
        else:
            raise Exception("Video file was not created")
            
    except Exception as e:
        logger.error(f"Error in video generation: {str(e)}")
        raise
    finally:
        # Clean up GPU memory
        if 'pipeline' in locals():
            del pipeline
        torch.cuda.empty_cache()

if __name__ == "__main__":
    try:
        video_path = test_simple_video_generation()
        print(f"\n🎉 SUCCESS! Video generated: {video_path}")
        print("📱 Memory-optimized video generation working!")
        print("🎬 Ready to scale up with larger models!")
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
