"""Content generation pipeline orchestration."""
import asyncio
from typing import Dict, List, Optional, Any
from pathlib import Path
import uuid
from loguru import logger
from moviepy.editor import VideoFileClip, concatenate_videoclips, CompositeVideoClip
import ffmpeg

from ..image_generation.generator import image_generator
from ..video_generation.generator import video_generator
from ..utils.config import config
from ..utils.storage import storage


class ContentPipeline:
    """Orchestrates the entire content generation pipeline."""
    
    def __init__(self):
        """Initialize the content pipeline."""
        self.trigger_word = config.get("lora.trigger_word", "sks woman")
        
    def create_content_from_concept(
        self,
        concept: str,
        lora_name: str,
        num_videos: int = 3,
        content_type: str = "social_media_post"
    ) -> Dict[str, Any]:
        """Create content from a high-level concept.
        
        Args:
            concept: High-level content concept (e.g. "talking about coffee")
            lora_name: LoRA model to use for character consistency
            num_videos: Number of video clips to generate
            content_type: Type of content to create
            
        Returns:
            Dictionary with generated content paths and metadata
        """
        logger.info(f"Creating content from concept: '{concept}'")
        
        # Generate prompts based on concept
        prompts = self._generate_prompts_from_concept(concept, num_videos)
        
        # Generate videos
        video_paths = []
        for i, prompt in enumerate(prompts):
            try:
                logger.info(f"Generating video {i+1}/{len(prompts)}: {prompt}")
                
                video_path = video_generator.generate_video_from_prompt_and_image(
                    prompt=prompt,
                    image_generator=image_generator,
                    lora_name=lora_name,
                    video_generation_kwargs={
                        "filename": f"content_{uuid.uuid4().hex[:6]}_{i+1}.mp4"
                    }
                )
                video_paths.append(video_path)
                
            except Exception as e:
                logger.error(f"Failed to generate video {i+1}: {e}")
        
        # Compile final video if multiple clips
        final_video_path = None
        if len(video_paths) > 1:
            final_video_path = self._combine_videos(video_paths, concept)
        elif len(video_paths) == 1:
            final_video_path = video_paths[0]
        
        result = {
            "concept": concept,
            "lora_name": lora_name,
            "content_type": content_type,
            "individual_videos": video_paths,
            "final_video": final_video_path,
            "prompts_used": prompts,
            "success": final_video_path is not None
        }
        
        logger.info(f"Content creation {'successful' if result['success'] else 'failed'}")
        return result
    
    def _generate_prompts_from_concept(self, concept: str, num_prompts: int) -> List[str]:
        """Generate specific prompts from a high-level concept.
        
        Args:
            concept: High-level concept
            num_prompts: Number of prompts to generate
            
        Returns:
            List of specific prompts
        """
        base_prompt = f"photo of {self.trigger_word}"
        
        # Concept-based prompt variations
        concept_variations = {
            "coffee": [
                "holding a coffee cup, smiling, cozy cafe background",
                "sipping coffee, warm lighting, morning vibes",
                "pointing at coffee beans, excited expression"
            ],
            "fashion": [
                "trying on stylish outfit, mirror selfie pose",
                "walking in fashionable clothes, city street",
                "showing off new accessories, bright lighting"
            ],
            "fitness": [
                "in gym clothes, motivational pose, gym background",
                "doing yoga pose, peaceful expression, nature background",
                "holding water bottle, post-workout glow"
            ],
            "food": [
                "tasting delicious food, happy expression, restaurant setting",
                "cooking in kitchen, focused and smiling",
                "showing food to camera, enthusiastic gesture"
            ],
            "travel": [
                "with luggage, excited for adventure, airport/station",
                "taking selfie at landmark, tourist pose",
                "relaxing at beach/mountain, peaceful expression"
            ]
        }
        
        # Find matching variations or create generic ones
        variations = []
        for key, var_list in concept_variations.items():
            if key.lower() in concept.lower():
                variations.extend(var_list)
                break
        
        # If no specific variations found, create generic ones
        if not variations:
            variations = [
                f"{concept}, happy expression, well-lit background",
                f"{concept}, engaging with camera, dynamic pose",
                f"{concept}, professional lighting, confident look"
            ]
        
        # Select and format prompts
        selected_variations = variations[:num_prompts] if len(variations) >= num_prompts else variations * ((num_prompts // len(variations)) + 1)
        selected_variations = selected_variations[:num_prompts]
        
        prompts = [f"{base_prompt}, {variation}" for variation in selected_variations]
        
        logger.info(f"Generated {len(prompts)} prompts for concept: {concept}")
        return prompts
    
    def _combine_videos(self, video_paths: List[str], concept: str) -> str:
        """Combine multiple video clips into a single video.
        
        Args:
            video_paths: List of paths to video files
            concept: Concept for naming the final video
            
        Returns:
            Path to combined video
        """
        if not video_paths:
            return None
        
        try:
            logger.info(f"Combining {len(video_paths)} videos")
            
            # Load video clips
            clips = []
            for path in video_paths:
                if Path(path).exists():
                    clip = VideoFileClip(str(path))
                    clips.append(clip)
                else:
                    logger.warning(f"Video file not found: {path}")
            
            if not clips:
                logger.error("No valid video clips to combine")
                return None
            
            # Concatenate clips
            final_clip = concatenate_videoclips(clips, method="compose")
            
            # Save combined video
            filename = f"final_{concept.replace(' ', '_')}_{uuid.uuid4().hex[:6]}.mp4"
            output_path = storage.local_base_path / "final_videos" / filename
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            final_clip.write_videofile(
                str(output_path),
                fps=config.get("video_generation.fps", 7),
                codec='libx264',
                audio_codec='aac'
            )
            
            # Clean up
            final_clip.close()
            for clip in clips:
                clip.close()
            
            logger.info(f"Combined video saved: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Failed to combine videos: {e}")
            return None
    
    def generate_batch_content(
        self,
        concepts: List[str],
        lora_name: str,
        videos_per_concept: int = 2
    ) -> List[Dict[str, Any]]:
        """Generate content for multiple concepts in batch.
        
        Args:
            concepts: List of content concepts
            lora_name: LoRA model to use
            videos_per_concept: Number of videos per concept
            
        Returns:
            List of content generation results
        """
        results = []
        
        for i, concept in enumerate(concepts):
            logger.info(f"Processing concept {i+1}/{len(concepts)}: {concept}")
            
            try:
                result = self.create_content_from_concept(
                    concept=concept,
                    lora_name=lora_name,
                    num_videos=videos_per_concept
                )
                results.append(result)
                
            except Exception as e:
                logger.error(f"Failed to process concept '{concept}': {e}")
                results.append({
                    "concept": concept,
                    "success": False,
                    "error": str(e)
                })
        
        successful = sum(1 for r in results if r.get("success", False))
        logger.info(f"Batch processing complete: {successful}/{len(concepts)} successful")
        
        return results
    
    def create_character_showcase(
        self,
        lora_name: str,
        showcase_type: str = "personality"
    ) -> Dict[str, Any]:
        """Create a showcase video demonstrating the character.
        
        Args:
            lora_name: LoRA model to use
            showcase_type: Type of showcase (personality, fashion, etc.)
            
        Returns:
            Dictionary with showcase content paths and metadata
        """
        showcase_concepts = {
            "personality": [
                "smiling warmly at camera, friendly expression",
                "laughing genuinely, joyful moment",
                "looking thoughtful, contemplative mood",
                "winking playfully, fun personality"
            ],
            "fashion": [
                "casual outfit, relaxed style",
                "formal attire, professional look",
                "trendy streetwear, urban vibe",
                "elegant evening dress, glamorous"
            ],
            "lifestyle": [
                "morning routine, getting ready",
                "working at computer, focused",
                "exercising, healthy lifestyle",
                "relaxing at home, cozy atmosphere"
            ]
        }
        
        prompts = showcase_concepts.get(showcase_type, showcase_concepts["personality"])
        full_prompts = [f"photo of {self.trigger_word}, {prompt}" for prompt in prompts]
        
        return self.create_content_from_concept(
            concept=f"{showcase_type}_showcase",
            lora_name=lora_name,
            num_videos=len(full_prompts)
        )
    
    def cleanup(self):
        """Clean up resources."""
        image_generator.cleanup()
        video_generator.cleanup()
        logger.info("Pipeline cleanup complete")


# Global pipeline instance
content_pipeline = ContentPipeline()
