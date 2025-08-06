#!/usr/bin/env python3
import sys
import os
import torch
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from ai_video_generator import AIVideoGenerator
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_test_portrait():
    """Create a realistic test portrait for video generation"""
    # Create a high-quality portrait-style image
    width, height = 1024, 576
    
    # Create base image with gradient background
    img = Image.new("RGB", (width, height), (25, 30, 45))
    draw = ImageDraw.Draw(img)
    
    # Create gradient background
    for y in range(height):
        color_val = int(25 + (y / height) * 30)
        draw.line([(0, y), (width, y)], fill=(color_val, color_val + 5, color_val + 15))
    
    # Create a person silhouette in center
    center_x, center_y = width // 2, height // 2
    
    # Head (oval)
    head_width, head_height = 180, 220
    head_bbox = [
        center_x - head_width//2, center_y - head_height - 50,
        center_x + head_width//2, center_y - 50
    ]
    draw.ellipse(head_bbox, fill=(210, 180, 160), outline=(190, 160, 140))
    
    # Shoulders
    shoulder_points = [
        (center_x - 120, center_y - 20),
        (center_x - 80, center_y + 80),
        (center_x + 80, center_y + 80),
        (center_x + 120, center_y - 20)
    ]
    draw.polygon(shoulder_points, fill=(150, 120, 100))
    
    # Simple facial features
    # Eyes
    eye_y = center_y - 120
    draw.ellipse([center_x - 50, eye_y, center_x - 30, eye_y + 15], fill=(50, 50, 50))
    draw.ellipse([center_x + 30, eye_y, center_x + 50, eye_y + 15], fill=(50, 50, 50))
    
    # Nose
    nose_points = [(center_x, eye_y + 35), (center_x - 8, eye_y + 50), (center_x + 8, eye_y + 50)]
    draw.polygon(nose_points, fill=(190, 160, 140))
    
    # Mouth
    draw.ellipse([center_x - 20, eye_y + 70, center_x + 20, eye_y + 85], fill=(180, 120, 120))
    
    # Hair
    hair_bbox = [
        center_x - head_width//2 - 10, center_y - head_height - 60,
        center_x + head_width//2 + 10, center_y - head_height + 40
    ]
    draw.ellipse(hair_bbox, fill=(80, 60, 40))
    
    # Add some texture/noise for realism
    pixels = np.array(img)
    noise = np.random.normal(0, 5, pixels.shape).astype(np.int16)
    pixels = np.clip(pixels.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    img = Image.fromarray(pixels)
    
    # Save the test image
    test_image_path = "test_portrait.jpg"
    img.save(test_image_path, "JPEG", quality=95)
    logger.info(f"Created test portrait: {test_image_path}")
    
    return test_image_path

def test_video_generation():
    """Test the complete video generation pipeline"""
    try:
        logger.info("Starting AI Video Generation Test...")
        
        # Create test portrait
        test_image = create_test_portrait()
        
        # Initialize video generator
        logger.info("Initializing AI Video Generator...")
        generator = AIVideoGenerator()
        
        # Generate test video
        logger.info("Generating test video...")
        video_path = generator.generate_video(
            reference_image_path=test_image,
            person_id="test_model",
            num_frames=25,
            num_inference_steps=20,  # Slightly fewer steps for faster generation
            motion_bucket_id=127,    # Moderate motion
            fps=7,
            seed=42  # For reproducible results
        )
        
        logger.info(f"✅ Test video generated successfully: {video_path}")
        
        # Check file size
        if os.path.exists(video_path):
            file_size = os.path.getsize(video_path) / (1024 * 1024)  # MB
            logger.info(f"Video file size: {file_size:.2f} MB")
            
            # Get video info
            import subprocess
            try:
                result = subprocess.run([
                    "ffprobe", "-v", "quiet", "-print_format", "json", 
                    "-show_format", "-show_streams", video_path
                ], capture_output=True, text=True)
                if result.returncode == 0:
                    import json
                    info = json.loads(result.stdout)
                    duration = float(info["format"].get("duration", 0))
                    logger.info(f"Video duration: {duration:.2f} seconds")
            except Exception as e:
                logger.warning(f"Could not get video info: {e}")
        
        return video_path
        
    except Exception as e:
        logger.error(f"Error in video generation test: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        video_path = test_video_generation()
        print(f"\n🎉 SUCCESS! Test video generated: {video_path}")
        print("\n📱 This video is ready for social media use!")
        print("🎬 The AI Video Generation system is fully operational!")
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
