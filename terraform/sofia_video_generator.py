#!/usr/bin/env python3
"""
Sofia-Specific AI Video Generator with Prompt Control
Generates videos that look like Sofia based on input prompts
"""

import os
import torch
import numpy as np
from PIL import Image
from ai_video_generator import AIVideoGenerator
from transformers import StableDiffusionPipeline, DDIMScheduler
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SofiaVideoGenerator:
    """
    AI video generator system for creating realistic videos of Sofia
    """
    
    def __init__(self):
        """
        Initialize with Sofia's identity profile and video generation model
        """
        self.video_generator = AIVideoGenerator()
        self.identity_created = False

    def create_sofia_identity(self, images_dir: str):
        """
        Create Sofia's identity profile for realistic generation
        
        Args:
            images_dir: directory containing Sofia's reference images
        """
        images = [os.path.join(images_dir, file) for file in os.listdir(images_dir) if file.endswith('.png')]
        self.video_generator.create_person_identity('sofia', images)
        self.identity_created = True

    def generate_video(self, prompt: str, output_path: str) -> str:
        """
        Generate a video based on a prompt and Sofia's appearance
        
        Args:
            prompt: Description of the video scenario (e.g., "Sofia walking on a beach")
            output_path: Path to save the generated video
        
        Returns:
            Path to the generated video
        """
        if not self.identity_created:
            raise ValueError("Sofia's identity profile not created. Run create_sofia_identity() first.")

        # Use the prompt to generate an initial image using Stable Diffusion
        logger.info(f"Generating base image for prompt: '{prompt}'")
        image = self.generate_image_from_prompt(prompt)

        # Generate a video using the initial image and Sofia's identity
        logger.info("Generating video with Sofia's appearance")
        video_path = self.video_generator.generate_video(
            reference_image_path=image,
            person_id='sofia',
            num_frames=25,
            num_inference_steps=25,
            motion_bucket_id=120,
            fps=7,
            seed=42  # Fixed seed for reproducibility
        )

        # Move video to desired output path
        os.rename(video_path, output_path)
        logger.info(f"Video generated and saved to {output_path}")
        return output_path

    @staticmethod
    def generate_image_from_prompt(prompt: str) -> str:
        """
        Generate an image from a text prompt using Stable Diffusion
        
        Args:
            prompt: Text prompt for the desired image scenario
        
        Returns:
            Path to the generated image
        """
        # Initialize the pipeline for text-to-image generation
        model_id = "CompVis/stable-diffusion-v1-4"
        pipe = StableDiffusionPipeline.from_pretrained(model_id, revision="fp16", torch_dtype=torch.float16)
        pipe = pipe.to("cuda")

        # Generate the image
        with torch.no_grad():
            image_latents = pipe(prompt, num_inference_steps=50).sample
            image = pipe.decode_latents(image_latents)[0]

        # Save the generated image
        image_path = "sofia_prompt.jpg"
        Image.fromarray(np.uint8(image * 255)).save(image_path)

        logger.info(f"Generated image from prompt saved at {image_path}")
        return image_path


def main():
    """
    Example usage of Sofia-specific video generation
    """
    try:
        # Initialize Sofia video generator
        sofia_gen = SofiaVideoGenerator()

        # Create Sofia's identity
        image_directory = "/home/trainer/sofia_photos"
        sofia_gen.create_sofia_identity(image_directory)

        # Generate a video based on prompt
        output_video_path = sofia_gen.generate_video(
            prompt="Sofia modeling in a futuristic studio",
            output_path="sofia_futuristic_video.mp4"
        )

        print(f"\n🎬 Sofia's video generated: {output_video_path}")
    except Exception as e:
        logger.error(f"Error in Sofia video generation: {e}")

if __name__ == "__main__":
    main()

