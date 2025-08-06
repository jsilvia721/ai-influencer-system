#!/usr/bin/env python3
"""
Sofia Quality Video Generator
Memory-optimized enhanced system for high-quality, smooth, longer Sofia videos
"""

import os
import torch
import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
from typing import List, Dict, Tuple, Optional
import logging
from datetime import datetime
import glob
import random

# Enhanced imports
from face_identity_system import FaceIdentityPreserver
from diffusers import StableVideoDiffusionPipeline
from diffusers.utils import load_image, export_to_video

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SofiaQualityGenerator:
    """
    Memory-optimized Sofia video generator with enhanced quality and prompt integration
    """
    
    def __init__(self, sofia_photos_dir: str = "/home/trainer/sofia_photos"):
        """
        Initialize quality Sofia video generation system
        """
        self.photos_dir = sofia_photos_dir
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # Initialize face identity system
        logger.info("Initializing Face Identity System...")
        self.face_system = FaceIdentityPreserver()
        
        # Use standard SVD model for memory efficiency but with optimized settings
        logger.info("Loading optimized Stable Video Diffusion model...")
        self.video_pipeline = StableVideoDiffusionPipeline.from_pretrained(
            "stabilityai/stable-video-diffusion-img2vid",  # Standard model for memory efficiency
            torch_dtype=torch.float16,
            variant="fp16"
        )
        self.video_pipeline.to(self.device)
        self.video_pipeline.enable_model_cpu_offload()
        
        # Sofia's identity profile
        self.sofia_profile = None
        self.reference_photos = []
        
        logger.info("Sofia Quality Video System initialized!")
    
    def load_sofia_photos(self) -> List[str]:
        """Load Sofia's reference photos with quality filtering"""
        photo_patterns = ["*.png", "*.jpg", "*.jpeg"]
        photos = []
        
        for pattern in photo_patterns:
            photos.extend(glob.glob(os.path.join(self.photos_dir, pattern)))
        
        # Filter for high-quality photos
        quality_photos = []
        for photo in photos:
            try:
                img = Image.open(photo)
                if img.width >= 512 and img.height >= 512:
                    quality_photos.append(photo)
            except Exception as e:
                logger.warning(f"Could not process {photo}: {e}")
        
        self.reference_photos = quality_photos
        logger.info(f"Loaded {len(quality_photos)} high-quality Sofia photos")
        return quality_photos
    
    def create_sofia_identity_profile(self):
        """Create Sofia's enhanced identity profile"""
        if not self.reference_photos:
            self.load_sofia_photos()
        
        logger.info("Creating Sofia's identity profile...")
        self.sofia_profile = self.face_system.create_person_profile("sofia", self.reference_photos)
        
        if self.sofia_profile:
            logger.info(f"✅ Sofia's identity profile created!")
            logger.info(f"Consistency: {self.sofia_profile['embedding_consistency']:.4f}")
    
    def select_best_photo_for_prompt(self, prompt: str) -> str:
        """
        Intelligently select the best Sofia photo based on the prompt
        """
        if not self.reference_photos:
            self.load_sofia_photos()
        
        prompt_lower = prompt.lower()
        scored_photos = []
        
        for photo in self.reference_photos:
            score = 0
            photo_name = os.path.basename(photo).lower()
            
            # Score based on prompt keywords
            if any(word in prompt_lower for word in ["smile", "smiling", "happy", "cheerful"]):
                if any(word in photo_name for word in ["candid", "natural"]):
                    score += 3
            
            if any(word in prompt_lower for word in ["pose", "modeling", "fashion", "elegant"]):
                if "photography" in photo_name:
                    score += 3
            
            if any(word in prompt_lower for word in ["wave", "waving", "gesture", "hello"]):
                if "natural" in photo_name:
                    score += 2
            
            # Prefer certain high-quality photos
            if "natural" in photo_name or "candid" in photo_name:
                score += 1
            
            # Prefer photos with higher numbers (often better quality)
            if any(num in photo_name for num in ["201", "202", "196", "197"]):
                score += 1
            
            scored_photos.append((photo, score))
        
        # Sort by score and select best
        scored_photos.sort(key=lambda x: x[1], reverse=True)
        selected_photo = scored_photos[0][0] if scored_photos else random.choice(self.reference_photos)
        
        logger.info(f"Selected photo for prompt '{prompt[:40]}...': {os.path.basename(selected_photo)}")
        return selected_photo
    
    def enhance_reference_image(self, image_path: str, prompt: str) -> Image.Image:
        """
        Enhance reference image based on prompt for better video generation
        """
        # Load image
        image = load_image(image_path)
        image = image.convert("RGB")
        
        # Apply prompt-based enhancements
        prompt_lower = prompt.lower()
        
        # Enhance brightness and contrast for better video quality
        if any(word in prompt_lower for word in ["bright", "cheerful", "warm", "welcoming"]):
            enhancer = ImageEnhance.Brightness(image)
            image = enhancer.enhance(1.15)
            enhancer = ImageEnhance.Color(image)
            image = enhancer.enhance(1.1)
        
        # Enhance sharpness for clearer details
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(1.1)
        
        # Enhance contrast for better definition
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.05)
        
        # Resize to optimal dimensions
        target_width, target_height = 1024, 576
        
        # Calculate scaling to maintain aspect ratio
        original_width, original_height = image.size
        scale = min(target_width / original_width, target_height / original_height)
        
        new_width = int(original_width * scale)
        new_height = int(original_height * scale)
        
        # High-quality resize
        image = image.resize((new_width, new_height), Image.LANCZOS)
        
        # Create final image with smart background
        final_image = Image.new("RGB", (target_width, target_height), (35, 40, 45))
        paste_x = (target_width - new_width) // 2
        paste_y = (target_height - new_height) // 2
        final_image.paste(image, (paste_x, paste_y))
        
        logger.info(f"Enhanced image for better video quality")
        return final_image
    
    def interpolate_frames(self, frames: List[Image.Image], target_fps: int = 30) -> List[Image.Image]:
        """
        Interpolate frames to create smoother motion and higher FPS
        """
        if len(frames) < 2:
            return frames
        
        logger.info(f"Interpolating frames for {target_fps}fps smooth motion...")
        
        # Calculate interpolation factor
        original_fps = 7  # SVD default
        interpolation_factor = target_fps / original_fps
        
        if interpolation_factor <= 1:
            return frames
        
        interpolated_frames = []
        
        for i in range(len(frames) - 1):
            current_frame = np.array(frames[i])
            next_frame = np.array(frames[i + 1])
            
            # Add current frame
            interpolated_frames.append(frames[i])
            
            # Calculate number of interpolated frames needed
            num_interpolated = int(interpolation_factor) - 1
            
            # Create interpolated frames
            for j in range(1, num_interpolated + 1):
                alpha = j / (num_interpolated + 1)
                
                # Linear interpolation
                interpolated = (1 - alpha) * current_frame + alpha * next_frame
                interpolated_frames.append(Image.fromarray(interpolated.astype(np.uint8)))
        
        # Add last frame
        interpolated_frames.append(frames[-1])
        
        logger.info(f"Interpolated from {len(frames)} to {len(interpolated_frames)} frames")
        return interpolated_frames
    
    def enhance_video_quality(self, frames: List[Image.Image]) -> List[Image.Image]:
        """
        Apply post-processing to enhance video quality
        """
        logger.info("Applying video quality enhancements...")
        
        enhanced_frames = []
        
        for i, frame in enumerate(frames):
            # Convert to numpy for processing
            frame_array = np.array(frame)
            
            # Apply noise reduction
            frame_array = cv2.bilateralFilter(frame_array, 5, 50, 50)
            
            # Enhance sharpness slightly
            kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
            frame_array = cv2.filter2D(frame_array, -1, kernel * 0.1)
            frame_array = np.clip(frame_array, 0, 255)
            
            # Slight color enhancement
            frame_array = cv2.convertScaleAbs(frame_array, alpha=1.05, beta=2)
            
            enhanced_frames.append(Image.fromarray(frame_array.astype(np.uint8)))
        
        return enhanced_frames
    
    def generate_quality_sofia_video(
        self,
        prompt: str,
        duration_seconds: float = 15.0,
        motion_intensity: str = "medium",
        smooth_fps: int = 30,
        enhance_quality: bool = True,
        seed: Optional[int] = None
    ) -> str:
        """
        Generate high-quality Sofia video with prompt integration and smooth motion
        """
        try:
            logger.info(f"Generating quality Sofia video: '{prompt}'")
            logger.info(f"Target: {duration_seconds}s at {smooth_fps}fps with quality enhancement")
            
            # Ensure Sofia's identity profile exists
            if not self.sofia_profile:
                self.create_sofia_identity_profile()
            
            # Select best reference photo for the prompt
            reference_photo = self.select_best_photo_for_prompt(prompt)
            
            # Enhance the reference image
            reference_image = self.enhance_reference_image(reference_photo, prompt)
            
            # Configure motion based on prompt and intensity
            motion_buckets = {"low": 100, "medium": 130, "high": 160}
            motion_bucket_id = motion_buckets.get(motion_intensity, 130)
            
            # Adjust motion based on prompt keywords
            prompt_lower = prompt.lower()
            if any(word in prompt_lower for word in ["gentle", "slow", "calm", "subtle"]):
                motion_bucket_id = max(motion_bucket_id - 20, 80)
            elif any(word in prompt_lower for word in ["energetic", "dynamic", "active", "lively"]):
                motion_bucket_id = min(motion_bucket_id + 20, 170)
            
            # Set seed for reproducibility
            if seed is not None:
                torch.manual_seed(seed)
                np.random.seed(seed)
            
            # Calculate segments needed for duration
            frames_per_segment = 14  # Standard SVD
            segment_duration = frames_per_segment / 7.0  # 7fps default
            num_segments = max(1, int(duration_seconds / segment_duration))
            
            logger.info(f"Generating {num_segments} segments for {duration_seconds}s video")
            
            all_frames = []
            
            # Generate video segments with variation
            for segment in range(num_segments):
                logger.info(f"Generating segment {segment + 1}/{num_segments}")
                
                # Clear GPU memory
                torch.cuda.empty_cache()
                
                # Add slight variation to each segment
                segment_motion = motion_bucket_id + random.randint(-15, 15)
                segment_motion = max(70, min(180, segment_motion))
                
                with torch.no_grad():
                    frames = self.video_pipeline(
                        reference_image,
                        decode_chunk_size=2,  # Memory efficient
                        num_frames=frames_per_segment,
                        motion_bucket_id=segment_motion,
                        noise_aug_strength=0.01,  # Less noise for cleaner output
                        num_inference_steps=25,   # More steps for quality
                    ).frames[0]
                
                # Add frames (avoid first frame duplicates)
                if segment == 0:
                    all_frames.extend(frames)
                else:
                    all_frames.extend(frames[2:])  # Skip first 2 frames for smoother transitions
            
            # Apply quality enhancements
            if enhance_quality:
                all_frames = self.enhance_video_quality(all_frames)
            
            # Interpolate for smooth motion
            if smooth_fps > 7:
                all_frames = self.interpolate_frames(all_frames, smooth_fps)
            
            # Generate output filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            prompt_slug = "".join(c for c in prompt.lower() if c.isalnum() or c == " ").replace(" ", "_")[:25]
            output_filename = f"sofia_quality_{prompt_slug}_{timestamp}.mp4"
            
            # Export with quality settings
            logger.info(f"Exporting quality video to {output_filename}")
            export_to_video(all_frames, output_filename, fps=smooth_fps)
            
            # Verify results
            if os.path.exists(output_filename):
                file_size = os.path.getsize(output_filename) / (1024 * 1024)
                actual_duration = len(all_frames) / smooth_fps
                
                logger.info(f"✅ Quality Sofia video generated!")
                logger.info(f"File: {output_filename}")
                logger.info(f"Size: {file_size:.2f} MB")
                logger.info(f"Duration: {actual_duration:.1f} seconds")
                logger.info(f"Frames: {len(all_frames)} at {smooth_fps}fps")
                logger.info(f"Motion: {motion_intensity} (bucket {motion_bucket_id})")
                
                return output_filename
            else:
                raise Exception("Quality video file was not created")
        
        except Exception as e:
            logger.error(f"Error generating quality Sofia video: {str(e)}")
            raise
        finally:
            torch.cuda.empty_cache()

def main():
    """Test the quality Sofia video generator"""
    try:
        # Initialize quality system
        sofia_gen = SofiaQualityGenerator()
        
        # Generate quality video with specific prompt
        video_path = sofia_gen.generate_quality_sofia_video(
            prompt="Sofia smiling warmly and waving hello to the camera with a gentle, welcoming gesture",
            duration_seconds=12.0,
            motion_intensity="medium",
            smooth_fps=30,
            enhance_quality=True,
            seed=42
        )
        
        print(f"\n🎉 Quality Sofia video generated: {video_path}")
        print("🎬 This should be much smoother, longer, and higher quality!")
        print("📱 Perfect for social media with 30fps smooth motion!")
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise

if __name__ == "__main__":
    main()
