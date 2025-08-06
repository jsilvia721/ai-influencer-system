#!/usr/bin/env python3
"""
Basic usage example for the AI Influencer System.

This script demonstrates how to:
1. Generate individual images
2. Create videos from prompts
3. Generate content from high-level concepts
4. Create character showcases
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.image_generation.generator import image_generator
from src.video_generation.generator import video_generator
from src.orchestration.pipeline import content_pipeline
from src.utils.storage import storage
from loguru import logger


def main():
    """Run basic usage examples."""
    logger.info("🎬 AI Influencer System - Basic Usage Examples")
    logger.info("=" * 60)
    
    # Check if we have any LoRA models
    loras = storage.list_loras()
    if not loras:
        logger.error("❌ No LoRA models found in data/loras/")
        logger.info("💡 Please add your trained LoRA (.safetensors) files to data/loras/")
        logger.info("💡 You can continue with examples that don't require LoRA")
        lora_name = None
    else:
        lora_name = loras[0]
        logger.info(f"✅ Using LoRA: {lora_name}")
    
    print("\n" + "="*60)
    print("Example 1: Generate a Single Image")
    print("="*60)
    
    try:
        prompt = "portrait of a woman, professional headshot, studio lighting, high quality"
        if lora_name:
            # Add trigger word for LoRA
            from src.utils.config import config
            trigger_word = config.get("lora.trigger_word", "sks woman")
            prompt = f"photo of {trigger_word}, professional headshot, studio lighting, high quality"
        
        logger.info(f"Generating image with prompt: {prompt}")
        
        image_path = image_generator.generate_image(
            prompt=prompt,
            lora_name=lora_name,
            num_inference_steps=20,
            seed=42,  # For reproducible results
            filename="example_portrait.png"
        )
        
        logger.success(f"✅ Image generated: {image_path}")
        
    except Exception as e:
        logger.error(f"❌ Image generation failed: {e}")
    
    print("\n" + "="*60)
    print("Example 2: Generate Video from Image")
    print("="*60)
    
    try:
        # First generate an image for the video
        prompt = "woman in casual clothes, sitting in a cozy cafe, warm lighting"
        if lora_name:
            from src.utils.config import config
            trigger_word = config.get("lora.trigger_word", "sks woman")
            prompt = f"photo of {trigger_word}, sitting in a cozy cafe, warm lighting"
        
        logger.info(f"Generating image for video: {prompt}")
        
        image_path = image_generator.generate_image(
            prompt=prompt,
            lora_name=lora_name,
            num_inference_steps=15,
            filename="cafe_scene.png"
        )
        
        logger.info("Creating video from image...")
        video_path = video_generator.generate_video_from_image(
            image=image_path,
            num_frames=16,  # Short video for example
            filename="cafe_scene_video.mp4"
        )
        
        logger.success(f"✅ Video generated: {video_path}")
        
    except Exception as e:
        logger.error(f"❌ Video generation failed: {e}")
    
    print("\n" + "="*60)
    print("Example 3: Create Content from Concept")
    print("="*60)
    
    if lora_name:
        try:
            concept = "morning coffee routine"
            logger.info(f"Creating content for concept: '{concept}'")
            
            result = content_pipeline.create_content_from_concept(
                concept=concept,
                lora_name=lora_name,
                num_videos=2,  # Generate 2 videos
                content_type="lifestyle_content"
            )
            
            if result["success"]:
                logger.success("✅ Content creation successful!")
                logger.info(f"Final video: {result['final_video']}")
                logger.info(f"Individual videos: {len(result['individual_videos'])}")
                for i, video in enumerate(result['individual_videos'], 1):
                    logger.info(f"  {i}. {video}")
            else:
                logger.error("❌ Content creation failed")
                
        except Exception as e:
            logger.error(f"❌ Content creation failed: {e}")
    else:
        logger.warning("⚠️ Skipping content creation - no LoRA available")
    
    print("\n" + "="*60)
    print("Example 4: Character Showcase")
    print("="*60)
    
    if lora_name:
        try:
            showcase_type = "personality"
            logger.info(f"Creating {showcase_type} showcase...")
            
            result = content_pipeline.create_character_showcase(
                lora_name=lora_name,
                showcase_type=showcase_type
            )
            
            if result["success"]:
                logger.success(f"✅ {showcase_type.title()} showcase created!")
                logger.info(f"Showcase video: {result['final_video']}")
            else:
                logger.error("❌ Showcase creation failed")
                
        except Exception as e:
            logger.error(f"❌ Showcase creation failed: {e}")
    else:
        logger.warning("⚠️ Skipping showcase - no LoRA available")
    
    print("\n" + "="*60)
    print("Example 5: Batch Content Generation")
    print("="*60)
    
    if lora_name:
        try:
            concepts = ["fitness motivation", "healthy breakfast", "productivity tips"]
            logger.info(f"Creating batch content for {len(concepts)} concepts...")
            
            results = content_pipeline.generate_batch_content(
                concepts=concepts,
                lora_name=lora_name,
                videos_per_concept=1  # 1 video per concept for speed
            )
            
            successful = sum(1 for r in results if r.get("success", False))
            logger.info(f"Batch processing completed: {successful}/{len(concepts)} successful")
            
            for result in results:
                concept = result["concept"]
                status = "✅" if result.get("success", False) else "❌"
                logger.info(f"  {status} {concept}")
                if result.get("final_video"):
                    logger.info(f"    Video: {result['final_video']}")
                    
        except Exception as e:
            logger.error(f"❌ Batch content generation failed: {e}")
    else:
        logger.warning("⚠️ Skipping batch generation - no LoRA available")
    
    print("\n" + "="*60)
    print("🎉 Examples Complete!")
    print("="*60)
    
    logger.info("Check the data/ directory for generated content:")
    logger.info("  - Images: data/images/")
    logger.info("  - Videos: data/video_clips/")
    logger.info("  - Final videos: data/final_videos/")
    
    logger.info("\n💡 Next steps:")
    logger.info("  - Start the API server: python -m src.api.main")
    logger.info("  - Visit the web interface: http://localhost:8000/docs")
    logger.info("  - Train your own LoRA for consistent characters")


if __name__ == "__main__":
    # Set up logging
    logger.remove()
    logger.add(
        sys.stdout, 
        level="INFO", 
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}"
    )
    
    main()
