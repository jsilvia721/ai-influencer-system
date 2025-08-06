#!/usr/bin/env python3
"""
Sofia Video Generation System
Creates videos that look like Sofia using her reference photos
"""

import os
import torch
import cv2
import numpy as np
from PIL import Image
from typing import List, Dict, Tuple, Optional
import logging
from datetime import datetime
import glob
import random

# Import our systems
from face_identity_system import FaceIdentityPreserver
from diffusers import StableVideoDiffusionPipeline
from diffusers.utils import load_image, export_to_video

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SofiaVideoSystem:
    """
    Complete video generation system specifically for Sofia
    """
    
    def __init__(self, sofia_photos_dir: str = "/home/trainer/sofia_photos"):
        """
        Initialize Sofia video generation system
        
        Args:
            sofia_photos_dir: Directory containing Sofia's reference photos
        """
        self.photos_dir = sofia_photos_dir
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # Initialize face identity system
        logger.info("Initializing Face Identity System...")
        self.face_system = FaceIdentityPreserver()
        
        # Initialize video pipeline (using standard SVD to save memory)
        logger.info("Loading Stable Video Diffusion model...")
        self.video_pipeline = StableVideoDiffusionPipeline.from_pretrained(
            "stabilityai/stable-video-diffusion-img2vid",
            torch_dtype=torch.float16,
            variant="fp16"
        )
        self.video_pipeline.to(self.device)
        self.video_pipeline.enable_model_cpu_offload()
        
        # Sofia's identity profile
        self.sofia_profile = None
        self.reference_photos = []
        
        logger.info("Sofia Video System initialized!")
    
    def load_sofia_photos(self) -> List[str]:
        """
        Load all of Sofia's reference photos
        
        Returns:
            List of photo file paths
        """
        photo_patterns = ["*.png", "*.jpg", "*.jpeg"]
        photos = []
        
        for pattern in photo_patterns:
            photos.extend(glob.glob(os.path.join(self.photos_dir, pattern)))
        
        self.reference_photos = photos
        logger.info(f"Loaded {len(photos)} Sofia photos")
        return photos
    
    def create_sofia_identity_profile(self):
        """
        Create Sofia's identity profile from her reference photos
        """
        if not self.reference_photos:
            self.load_sofia_photos()
        
        if not self.reference_photos:
            raise ValueError(f"No photos found in {self.photos_dir}")
        
        logger.info("Creating Sofia's identity profile...")
        self.sofia_profile = self.face_system.create_person_profile("sofia", self.reference_photos)
        
        if self.sofia_profile:
            logger.info(f"✅ Sofia's identity profile created successfully!")
            logger.info(f"Profile consistency: {self.sofia_profile['embedding_consistency']:.4f}")
            logger.info(f"Reference images: {len(self.sofia_profile['reference_images'])}")
        else:
            raise ValueError("Failed to create Sofia's identity profile")
    
    def select_best_reference_photo(self, activity_hint: str = None) -> str:
        """
        Select the best reference photo for video generation
        
        Args:
            activity_hint: Hint about the desired activity/pose
            
        Returns:
            Path to the selected reference photo
        """
        if not self.reference_photos:
            self.load_sofia_photos()
        
        # For now, select a random high-quality photo
        # In the future, we could use AI to select based on activity_hint
        selected_photo = random.choice(self.reference_photos)
        logger.info(f"Selected reference photo: {os.path.basename(selected_photo)}")
        return selected_photo
    
    def preprocess_reference_image(self, image_path: str) -> Image.Image:
        """
        Preprocess reference image for optimal video generation
        
        Args:
            image_path: Path to the reference image
            
        Returns:
            Preprocessed PIL Image
        """
        # Load image
        image = load_image(image_path)
        image = image.convert("RGB")
        
        # Resize to optimal size for video generation (1024x576)
        target_width, target_height = 1024, 576
        
        # Calculate scaling to maintain aspect ratio
        original_width, original_height = image.size
        scale = min(target_width / original_width, target_height / original_height)
        
        new_width = int(original_width * scale)
        new_height = int(original_height * scale)
        
        # Resize image
        image = image.resize((new_width, new_height), Image.LANCZOS)
        
        # Create final image with target size (centered)
        final_image = Image.new("RGB", (target_width, target_height), (0, 0, 0))
        paste_x = (target_width - new_width) // 2
        paste_y = (target_height - new_height) // 2
        final_image.paste(image, (paste_x, paste_y))
        
        logger.info(f"Preprocessed image: {image_path} -> {target_width}x{target_height}")
        return final_image
    
    def generate_sofia_video(
        self,
        activity_description: str = "Sofia posing elegantly",
        num_frames: int = 14,
        motion_intensity: str = "medium",
        seed: Optional[int] = None
    ) -> str:
        """
        Generate a video of Sofia based on activity description
        
        Args:
            activity_description: Description of what Sofia should be doing
            num_frames: Number of frames to generate (max 14 for standard SVD)
            motion_intensity: "low", "medium", or "high"
            seed: Random seed for reproducibility
            
        Returns:
            Path to the generated video
        """
        try:
            logger.info(f"Generating Sofia video: '{activity_description}'")
            
            # Ensure Sofia's identity profile exists
            if not self.sofia_profile:
                self.create_sofia_identity_profile()
            
            # Select best reference photo
            reference_photo = self.select_best_reference_photo(activity_description)
            
            # Preprocess the reference image
            reference_image = self.preprocess_reference_image(reference_photo)
            
            # Set motion bucket based on intensity
            motion_buckets = {"low": 80, "medium": 127, "high": 180}
            motion_bucket_id = motion_buckets.get(motion_intensity, 127)
            
            # Set seed for reproducibility
            if seed is not None:
                torch.manual_seed(seed)
                np.random.seed(seed)
            
            # Generate video
            logger.info(f"Generating {num_frames} frames with {motion_intensity} motion...")
            
            # Clear GPU memory
            torch.cuda.empty_cache()
            
            with torch.no_grad():
                frames = self.video_pipeline(
                    reference_image,
                    decode_chunk_size=2,
                    num_frames=num_frames,
                    motion_bucket_id=motion_bucket_id,
                    noise_aug_strength=0.02,
                    num_inference_steps=20,
                ).frames[0]
            
            # Generate output filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            activity_slug = activity_description.lower().replace(" ", "_")[:20]
            output_filename = f"sofia_{activity_slug}_{timestamp}.mp4"
            
            # Export video
            logger.info(f"Exporting Sofia video to {output_filename}")
            export_to_video(frames, output_filename, fps=7)
            
            # Verify output
            if os.path.exists(output_filename):
                file_size = os.path.getsize(output_filename) / (1024 * 1024)
                duration = num_frames / 7.0
                
                logger.info(f"✅ Sofia video generated successfully!")
                logger.info(f"File: {output_filename}")
                logger.info(f"Size: {file_size:.2f} MB")
                logger.info(f"Duration: {duration:.1f} seconds")
                logger.info(f"Frames: {len(frames)}")
                
                return output_filename
            else:
                raise Exception("Video file was not created")
        
        except Exception as e:
            logger.error(f"Error generating Sofia video: {str(e)}")
            raise
        finally:
            # Clean up GPU memory
            torch.cuda.empty_cache()
    
    def batch_generate_videos(self, scenarios: List[str], **kwargs) -> List[str]:
        """
        Generate multiple videos for different scenarios
        
        Args:
            scenarios: List of activity descriptions
            **kwargs: Additional arguments for generate_sofia_video
            
        Returns:
            List of generated video paths
        """
        generated_videos = []
        
        for i, scenario in enumerate(scenarios):
            logger.info(f"Generating video {i+1}/{len(scenarios)}: {scenario}")
            try:
                video_path = self.generate_sofia_video(scenario, **kwargs)
                generated_videos.append(video_path)
            except Exception as e:
                logger.error(f"Failed to generate video for '{scenario}': {str(e)}")
                continue
        
        logger.info(f"Batch generation completed: {len(generated_videos)}/{len(scenarios)} videos")
        return generated_videos

def main():
    """
    Example usage of Sofia Video System
    """
    try:
        # Initialize Sofia video system
        sofia_system = SofiaVideoSystem()
        
        # Example scenarios to generate
        scenarios = [
            "Sofia smiling and waving",
            "Sofia posing confidently", 
            "Sofia looking thoughtful",
            "Sofia in a modeling pose"
        ]
        
        # Generate a single video
        video_path = sofia_system.generate_sofia_video(
            activity_description="Sofia posing elegantly for a photoshoot",
            motion_intensity="medium",
            seed=42
        )
        
        print(f"\n🎉 Sofia video generated: {video_path}")
        print("🎬 The video should now look like Sofia from your photos!")
        
    except Exception as e:
        logger.error(f"Error in Sofia video generation: {str(e)}")
        raise

if __name__ == "__main__":
    main()
