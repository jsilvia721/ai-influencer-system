#!/usr/bin/env python3
"""
Fixed Memory-Optimized AI Video Generator Test
Uses correct diffusers API for Stable Video Diffusion
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
    # Create standard SVD input size
    width, height = 1024, 576
    
    # Create base image
    img = Image.new("RGB", (width, height), (45, 55, 75))
    draw = ImageDraw.Draw(img)
    
    # Simple gradient background
    for y in range(height):
        color_val = int(45 + (y / height) * 40)
        draw.line([(0, y), (width, y)], fill=(color_val, color_val + 10, color_val + 20))
    
    # Simple person-like figure
    center_x, center_y = width // 2, height // 2
    
    # Head
    head_size = 120
    draw.ellipse([
        center_x - head_size, center_y - head_size - 50,
        center_x + head_size, center_y + head_size - 50
    ], fill=(200, 170, 150))
    
    # Body/shoulders
    shoulder_width = 150
    draw.rectangle([
        center_x - shoulder_width, center_y + 20,
        center_x + shoulder_width, center_y + 200
    ], fill=(120, 100, 80))
    
    # Simple facial features
    # Eyes
    eye_size = 12
    draw.ellipse([center_x - 40, center_y - 80, center_x - 40 + eye_size, center_y - 80 + eye_size], fill=(0, 0, 0))
    draw.ellipse([center_x + 40, center_y - 80, center_x + 40 + eye_size, center_y - 80 + eye_size], fill=(0, 0, 0))
    
    # Mouth
    draw.ellipse([center_x - 20, center_y - 30, center_x + 20, center_y - 15], fill=(150, 100, 100))
    
    # Save the test image
    test_image_path = "simple_test.jpg"
    img.save(test_image_path, "JPEG", quality=90)
    logger.info(f"Created simple test image: {test_image_path}")
    
    return test_image_path

def test_simple_video_generation():
    """Test video generation with minimal memory usage"""
    pipeline = None
    try:
        logger.info("Starting memory-optimized video generation test...")
        
        # Create simple test image
        test_image = create_simple_test_image()
        
        # Initialize with memory optimizations
        logger.info("Loading Stable Video Diffusion with memory optimizations...")
        
        # Use the standard SVD model (not XT to save memory)
        pipeline = StableVideoDiffusionPipeline.from_pretrained(
            "stabilityai/stable-video-diffusion-img2vid",
            torch_dtype=torch.float16,
            variant="fp16"
        )
        
        # Memory optimizations
        pipeline.to("cuda")
        pipeline.enable_model_cpu_offload()
        
        # Try to enable additional optimizations if available
        try:
            if hasattr(pipeline.vae, 'enable_slicing'):
                pipeline.vae.enable_slicing()
                logger.info("Enabled VAE slicing")
        except Exception as e:
            logger.warning(f"Could not enable VAE slicing: {e}")
        
        try:
            if hasattr(pipeline.vae, 'enable_tiling'):
                pipeline.vae.enable_tiling()
                logger.info("Enabled VAE tiling")
        except Exception as e:
            logger.warning(f"Could not enable VAE tiling: {e}")
        
        logger.info("Pipeline loaded with memory optimizations")
        
        # Load and preprocess image
        image = load_image(test_image)
        
        # Generate video with conservative settings
        logger.info("Generating video with conservative settings...")
        
        # Clear any existing GPU memory
        torch.cuda.empty_cache()
        
        with torch.no_grad():
            frames = pipeline(
                image,
                decode_chunk_size=2,      # Very small chunks
                num_frames=14,            # Fewer frames (standard SVD max)
                motion_bucket_id=100,     # Lower motion
                noise_aug_strength=0.02,  # Minimal noise
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
        if pipeline is not None:
            del pipeline
        torch.cuda.empty_cache()
        logger.info("Cleaned up GPU memory")

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
