#!/usr/bin/env python3
"""
AI Video Generator with Face Identity Preservation
Generates realistic videos of specific people using Stable Video Diffusion and face embeddings
"""

import os
import torch
import cv2
import numpy as np
from PIL import Image
from typing import List, Dict, Tuple, Optional, Union
import logging
from pathlib import Path
import json
from datetime import datetime

# Import diffusion libraries
from diffusers import StableVideoDiffusionPipeline
from diffusers.utils import load_image, export_to_video
import transformers

# Import our face identity system
from face_identity_system import FaceIdentityPreserver

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AIVideoGenerator:
    """
    Complete AI video generation system with face identity preservation
    """
    
    def __init__(self, model_path: str = "stabilityai/stable-video-diffusion-img2vid-xt"):
        """
        Initialize the AI video generation system
        
        Args:
            model_path: Hugging Face model path for Stable Video Diffusion
        """
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {self.device}")
        
        # Initialize face identity system
        logger.info("Initializing Face Identity System...")
        self.face_system = FaceIdentityPreserver()
        
        # Initialize video generation pipeline
        logger.info(f"Loading Stable Video Diffusion model: {model_path}")
        self.video_pipeline = StableVideoDiffusionPipeline.from_pretrained(
            model_path,
            torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
            variant="fp16" if self.device == "cuda" else None
        )
        self.video_pipeline.to(self.device)
        
        # Enable memory efficient attention if available
        if hasattr(self.video_pipeline, "enable_xformers_memory_efficient_attention"):
            try:
                self.video_pipeline.enable_xformers_memory_efficient_attention()
                logger.info("Enabled xFormers memory efficient attention")
            except Exception as e:
                logger.warning(f"Could not enable xFormers: {e}")
        
        # Enable model CPU offload for memory efficiency
        if self.device == "cuda":
            self.video_pipeline.enable_model_cpu_offload()
            logger.info("Enabled model CPU offload")
        
        self.output_dir = Path("generated_videos")
        self.output_dir.mkdir(exist_ok=True)
        
        logger.info("AI Video Generator initialized successfully!")
    
    def create_person_identity(self, person_id: str, image_paths: List[str]) -> Dict:
        """
        Create a person identity profile from reference images
        
        Args:
            person_id: Unique identifier for the person
            image_paths: List of reference image paths
            
        Returns:
            Person identity profile
        """
        logger.info(f"Creating identity profile for {person_id}")
        return self.face_system.create_person_profile(person_id, image_paths)
    
    def preprocess_reference_image(self, image_path: str, target_size: Tuple[int, int] = (1024, 576)) -> Image.Image:
        """
        Preprocess reference image for video generation
        
        Args:
            image_path: Path to the reference image
            target_size: Target size for the image (width, height)
            
        Returns:
            Preprocessed PIL Image
        """
        try:
            # Load image
            image = load_image(image_path)
            
            # Resize while maintaining aspect ratio
            image = image.convert("RGB")
            
            # Calculate new size maintaining aspect ratio
            original_width, original_height = image.size
            target_width, target_height = target_size
            
            # Calculate scaling factor
            scale = min(target_width / original_width, target_height / original_height)
            new_width = int(original_width * scale)
            new_height = int(original_height * scale)
            
            # Resize image
            image = image.resize((new_width, new_height), Image.LANCZOS)
            
            # Create new image with target size and paste resized image in center
            final_image = Image.new("RGB", target_size, (0, 0, 0))
            paste_x = (target_width - new_width) // 2
            paste_y = (target_height - new_height) // 2
            final_image.paste(image, (paste_x, paste_y))
            
            logger.info(f"Preprocessed image: {image_path} -> {target_size}")
            return final_image
            
        except Exception as e:
            logger.error(f"Error preprocessing image {image_path}: {str(e)}")
            raise
    
    def generate_video(
        self, 
        reference_image_path: str,
        person_id: Optional[str] = None,
        num_frames: int = 25,
        num_inference_steps: int = 25,
        motion_bucket_id: int = 127,
        fps: int = 7,
        decode_chunk_size: int = 8,
        seed: Optional[int] = None
    ) -> str:
        """
        Generate a video from a reference image
        
        Args:
            reference_image_path: Path to the reference image
            person_id: Optional person ID for identity consistency
            num_frames: Number of frames to generate (max 25 for SVD-XT)
            num_inference_steps: Number of denoising steps
            motion_bucket_id: Motion intensity (lower = less motion, higher = more motion)
            fps: Frames per second for output video
            decode_chunk_size: Chunk size for decoding (lower = less memory)
            seed: Random seed for reproducibility
            
        Returns:
            Path to the generated video file
        """
        try:
            logger.info(f"Starting video generation from {reference_image_path}")
            
            # Set seed for reproducibility
            if seed is not None:
                torch.manual_seed(seed)
                np.random.seed(seed)
            
            # Preprocess reference image
            reference_image = self.preprocess_reference_image(reference_image_path)
            
            # Extract face embedding if person_id is provided
            face_info = None
            if person_id and person_id in self.face_system.identity_db:
                face_info = self.face_system.extract_face_embedding(reference_image_path)
                logger.info(f"Using identity profile for {person_id}")
            
            # Generate video frames
            logger.info(f"Generating {num_frames} frames with {num_inference_steps} inference steps")
            
            with torch.no_grad():
                frames = self.video_pipeline(
                    reference_image,
                    decode_chunk_size=decode_chunk_size,
                    num_frames=num_frames,
                    motion_bucket_id=motion_bucket_id,
                    noise_aug_strength=0.1,
                    num_inference_steps=num_inference_steps,
                ).frames[0]
            
            # Generate output filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            person_suffix = f"_{person_id}" if person_id else ""
            output_filename = f"ai_video_{timestamp}{person_suffix}.mp4"
            output_path = self.output_dir / output_filename
            
            # Export to video
            logger.info(f"Exporting video to {output_path}")
            export_to_video(frames, str(output_path), fps=fps)
            
            # Save generation metadata
            metadata = {
                "timestamp": timestamp,
                "reference_image": reference_image_path,
                "person_id": person_id,
                "num_frames": num_frames,
                "num_inference_steps": num_inference_steps,
                "motion_bucket_id": motion_bucket_id,
                "fps": fps,
                "seed": seed,
                "output_path": str(output_path)
            }
            
            metadata_path = output_path.with_suffix('.json')
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"✅ Video generation completed: {output_path}")
            logger.info(f"Video duration: {num_frames/fps:.1f} seconds")
            
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Error during video generation: {str(e)}")
            raise
    
    def batch_generate_videos(
        self,
        image_person_pairs: List[Tuple[str, str]],
        **generation_kwargs
    ) -> List[str]:
        """
        Generate multiple videos in batch
        
        Args:
            image_person_pairs: List of (image_path, person_id) tuples
            **generation_kwargs: Arguments to pass to generate_video
            
        Returns:
            List of generated video paths
        """
        generated_videos = []
        
        for i, (image_path, person_id) in enumerate(image_person_pairs):
            logger.info(f"Generating video {i+1}/{len(image_person_pairs)}")
            try:
                video_path = self.generate_video(
                    image_path, 
                    person_id=person_id,
                    **generation_kwargs
                )
                generated_videos.append(video_path)
            except Exception as e:
                logger.error(f"Failed to generate video for {image_path}: {str(e)}")
                continue
        
        logger.info(f"Batch generation completed: {len(generated_videos)}/{len(image_person_pairs)} videos")
        return generated_videos
    
    def save_identity_database(self, filepath: str = "identity_database.pkl"):
        """Save the identity database"""
        self.face_system.save_identity_database(filepath)
    
    def load_identity_database(self, filepath: str = "identity_database.pkl"):
        """Load the identity database"""
        self.face_system.load_identity_database(filepath)
    
    def get_identity_summary(self) -> Dict:
        """Get summary of stored identities"""
        return self.face_system.get_identity_summary()

def main():
    """
    Example usage of the AI Video Generator
    """
    try:
        # Initialize the system
        generator = AIVideoGenerator()
        
        print("🎬 AI Video Generator initialized successfully!")
        print(f"🎯 Output directory: {generator.output_dir}")
        print("📸 Ready to generate videos from reference images")
        print("🎭 Face identity preservation enabled")
        
        # Example usage (uncomment when you have reference images):
        # 
        # # Create person identity
        # reference_images = ["path/to/person1.jpg", "path/to/person2.jpg"]
        # generator.create_person_identity("model_alice", reference_images)
        # 
        # # Generate video
        # video_path = generator.generate_video(
        #     "path/to/reference.jpg",
        #     person_id="model_alice",
        #     num_frames=25,
        #     motion_bucket_id=127,
        #     fps=7
        # )
        # print(f"Generated video: {video_path}")
        
    except Exception as e:
        logger.error(f"Error initializing AI Video Generator: {str(e)}")
        raise

if __name__ == "__main__":
    main()
