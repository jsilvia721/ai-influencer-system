#!/usr/bin/env python3
"""
Script to generate consistent character training images using Replicate API
This creates 25 images of the same character for LoRA training
"""

import replicate
import requests
import os
from datetime import datetime
import time

# Set your Replicate API token
REPLICATE_API_TOKEN = "your_replicate_token_here"  # Replace with your actual token

def generate_character_images(character_description, output_dir="training_images"):
    """
    Generate 25 consistent images of a character for LoRA training
    
    Args:
        character_description (str): Description of the character
        output_dir (str): Directory to save images
    """
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    character_dir = os.path.join(output_dir, f"character_{timestamp}")
    os.makedirs(character_dir, exist_ok=True)
    
    # Base prompt for consistency
    base_prompt = f"{character_description}, photorealistic, high quality, professional photography"
    
    # Different poses and angles for variety
    variations = [
        "front view headshot, neutral expression",
        "three-quarter view, slight smile",
        "profile view, looking right",
        "front view, bright smile",
        "three-quarter view looking left",
        "close-up portrait, serious expression",
        "front view, laughing",
        "side profile, contemplative",
        "three-quarter view, surprised expression",
        "front view, confident pose",
        "profile view looking up",
        "front view with hands near face",
        "three-quarter view, thoughtful",
        "close-up, eyes closed peaceful",
        "front view, professional headshot",
        "three-quarter view, casual pose",
        "profile view, looking down",
        "front view, natural smile",
        "three-quarter view, intense gaze",
        "close-up portrait, soft lighting",
        "front view, warm expression",
        "side view, dramatic lighting",
        "three-quarter view, joyful",
        "front view, elegant pose",
        "profile silhouette, artistic"
    ]
    
    print(f"Generating 25 images for character: {character_description}")
    print(f"Output directory: {character_dir}")
    
    # Use a consistent seed for base character features
    seed = 42  # You can change this for different characters
    
    for i, variation in enumerate(variations, 1):
        full_prompt = f"{base_prompt}, {variation}"
        
        print(f"Generating image {i}/25: {variation}")
        
        try:
            # Generate image using Replicate
            output = replicate.run(
                "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
                input={
                    "prompt": full_prompt,
                    "seed": seed,  # Keep seed consistent for character consistency
                    "width": 1024,
                    "height": 1024,
                    "num_outputs": 1,
                    "guidance_scale": 7.5,
                    "num_inference_steps": 50
                }
            )
            
            # Download and save the image
            if output and len(output) > 0:
                image_url = output[0]
                response = requests.get(image_url)
                
                if response.status_code == 200:
                    filename = f"character_image_{i:02d}.jpg"
                    filepath = os.path.join(character_dir, filename)
                    
                    with open(filepath, 'wb') as f:
                        f.write(response.content)
                    
                    print(f"✓ Saved: {filename}")
                else:
                    print(f"✗ Failed to download image {i}")
            
            # Small delay to avoid rate limiting
            time.sleep(2)
            
        except Exception as e:
            print(f"✗ Error generating image {i}: {str(e)}")
            continue
    
    print(f"\nCompleted! Images saved in: {character_dir}")
    print(f"You can now upload these 25 images to your character training interface.")

def main():
    # Example character description
    character_description = (
        "attractive latina woman, 25 years old, warm brown eyes, "
        "long dark wavy hair, natural makeup, olive skin tone, "
        "elegant features, confident expression"
    )
    
    print("Character Training Image Generator")
    print("=" * 50)
    
    # You can customize the character description here
    custom_description = input(f"Enter character description (or press Enter to use default):\nDefault: {character_description}\n\nYour description: ").strip()
    
    if custom_description:
        character_description = custom_description
    
    print(f"\nUsing description: {character_description}")
    
    # Set your Replicate API token
    replicate_token = input(f"\nEnter your Replicate API token: ").strip()
    if replicate_token:
        os.environ["REPLICATE_API_TOKEN"] = replicate_token
    else:
        print("Warning: No API token provided. Make sure REPLICATE_API_TOKEN is set in your environment.")
    
    # Generate the images
    generate_character_images(character_description)

if __name__ == "__main__":
    main()
