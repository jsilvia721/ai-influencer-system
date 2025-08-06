"""Video generation using Stable Video Diffusion."""
import torch
from diffusers import StableVideoDiffusionPipeline
from diffusers.utils import load_image, export_to_video
from PIL import Image
from typing import Optional, Union, List
from pathlib import Path
import uuid
import tempfile
from loguru import logger

from ..utils.config import config
from ..utils.storage import storage


class VideoGenerator:
    """Generates videos using Stable Video Diffusion."""
    
    def __init__(self):
        """Initialize the video generator."""
        self.pipeline = None
        self.device = config.get("models.stable_video_diffusion.device", "cpu")
        self.model_id = config.get("models.stable_video_diffusion.model_id", "stabilityai/stable-video-diffusion-img2vid-xt")
        
        # Ensure storage directories exist
        storage.ensure_local_dirs()
    
    def load_pipeline(self):
        """Load the Stable Video Diffusion pipeline."""
        if self.pipeline is not None:
            logger.info("Video pipeline already loaded")
            return
        
        logger.info(f"Loading Stable Video Diffusion pipeline: {self.model_id}")
        
        # Load pipeline
        self.pipeline = StableVideoDiffusionPipeline.from_pretrained(
            self.model_id,
            torch_dtype=torch.float16 if self.device != "cpu" else torch.float32,
            variant="fp16" if self.device != "cpu" else None,
        )
        
        # Move to device
        self.pipeline = self.pipeline.to(self.device)
        
        # Enable memory efficient attention if using CUDA
        if self.device == "cuda":
            self.pipeline.enable_model_cpu_offload()
        
        logger.info(f"Video pipeline loaded on device: {self.device}")
    
    def generate_video_from_image(
        self,
        image: Union[str, Image.Image, Path],
        width: Optional[int] = None,
        height: Optional[int] = None,
        num_frames: Optional[int] = None,
        fps: Optional[int] = None,
        motion_bucket_id: Optional[int] = None,
        noise_aug_strength: Optional[float] = None,
        num_inference_steps: int = 25,
        seed: Optional[int] = None,
        save_video: bool = True,
        filename: Optional[str] = None
    ) -> Union[List[Image.Image], str]:
        """Generate a video from an input image.
        
        Args:
            image: Input image (path, PIL Image, or pathlib.Path)
            width: Video width (defaults to config)
            height: Video height (defaults to config)
            num_frames: Number of frames to generate (defaults to config)
            fps: Frames per second (defaults to config)
            motion_bucket_id: Motion strength (higher = more motion)
            noise_aug_strength: Noise augmentation strength
            num_inference_steps: Number of denoising steps
            seed: Random seed for reproducible generation
            save_video: Whether to save the video to storage
            filename: Custom filename (auto-generated if None)
            
        Returns:
            List of PIL Images or path to saved video if save_video=True
        """
        if self.pipeline is None:
            self.load_pipeline()
        
        # Load and prepare image
        if isinstance(image, (str, Path)):
            image = load_image(str(image))
        elif not isinstance(image, Image.Image):
            raise ValueError("Image must be a PIL Image, file path, or pathlib.Path")
        
        # Use config defaults if not specified
        width = width or config.get("video_generation.width", 576)
        height = height or config.get("video_generation.height", 1024)
        num_frames = num_frames or config.get("video_generation.num_frames", 25)
        fps = fps or config.get("video_generation.fps", 7)
        motion_bucket_id = motion_bucket_id or config.get("video_generation.motion_bucket_id", 127)
        noise_aug_strength = noise_aug_strength or config.get("video_generation.noise_aug_strength", 0.02)
        
        # Resize image to match video dimensions
        image = image.resize((width, height), Image.Resampling.LANCZOS)
        
        # Set seed if provided
        if seed is not None:
            torch.manual_seed(seed)
            if torch.cuda.is_available():
                torch.cuda.manual_seed(seed)
        
        logger.info(f"Generating video from image: {width}x{height}, {num_frames} frames at {fps} fps")
        logger.info(f"Motion strength: {motion_bucket_id}, noise: {noise_aug_strength}")
        
        try:
            # Generate video frames
            frames = self.pipeline(
                image,
                width=width,
                height=height,
                num_frames=num_frames,
                motion_bucket_id=motion_bucket_id,
                fps=fps,
                noise_aug_strength=noise_aug_strength,
                num_inference_steps=num_inference_steps,
                decode_chunk_size=8,
            ).frames[0]
            
            if save_video:
                # Generate filename if not provided
                if filename is None:
                    filename = f"video_{uuid.uuid4().hex[:8]}.mp4"
                elif not filename.endswith(('.mp4', '.avi', '.mov')):
                    filename += '.mp4'
                
                # Create temporary video file
                with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
                    temp_path = temp_file.name
                
                # Export frames to video
                export_to_video(frames, temp_path, fps=fps)
                
                # Save to storage
                saved_path = storage.save_video(temp_path, filename)
                
                # Clean up temporary file
                Path(temp_path).unlink(missing_ok=True)
                
                logger.info(f"Generated and saved video: {saved_path}")
                return saved_path
            else:
                logger.info(f"Generated video with {len(frames)} frames (not saved)")
                return frames
                
        except Exception as e:
            logger.error(f"Failed to generate video: {e}")
            raise
    
    def generate_video_from_prompt_and_image(
        self,
        prompt: str,
        image_generator,
        lora_name: Optional[str] = None,
        image_generation_kwargs: Optional[dict] = None,
        video_generation_kwargs: Optional[dict] = None
    ) -> str:
        """Generate a video by first creating an image from a prompt, then animating it.
        
        Args:
            prompt: Text prompt for image generation
            image_generator: ImageGenerator instance
            lora_name: LoRA model to use for image generation
            image_generation_kwargs: Additional kwargs for image generation
            video_generation_kwargs: Additional kwargs for video generation
            
        Returns:
            Path to saved video
        """
        logger.info(f"Generating video from prompt: '{prompt[:50]}...'")
        
        # Default kwargs
        image_kwargs = image_generation_kwargs or {}
        video_kwargs = video_generation_kwargs or {}
        
        try:
            # Generate image first
            image_path = image_generator.generate_image(
                prompt=prompt,
                lora_name=lora_name,
                save_image=True,
                filename=f"temp_image_{uuid.uuid4().hex[:8]}.png",
                **image_kwargs
            )
            
            # Generate video from image
            video_path = self.generate_video_from_image(
                image=image_path,
                save_video=True,
                **video_kwargs
            )
            
            # Clean up temporary image
            Path(image_path).unlink(missing_ok=True)
            
            logger.info(f"Generated video from prompt: {video_path}")
            return video_path
            
        except Exception as e:
            logger.error(f"Failed to generate video from prompt: {e}")
            raise
    
    def generate_character_videos(
        self,
        prompts: List[str],
        image_generator,
        lora_name: str,
        **kwargs
    ) -> List[str]:
        """Generate multiple character videos from prompts.
        
        Args:
            prompts: List of text prompts
            image_generator: ImageGenerator instance
            lora_name: LoRA model to use
            **kwargs: Additional arguments for video generation
            
        Returns:
            List of paths to saved videos
        """
        generated_paths = []
        
        for i, prompt in enumerate(prompts):
            try:
                filename = f"character_video_{i+1}_{uuid.uuid4().hex[:6]}.mp4"
                
                path = self.generate_video_from_prompt_and_image(
                    prompt=prompt,
                    image_generator=image_generator,
                    lora_name=lora_name,
                    video_generation_kwargs={"filename": filename, **kwargs}
                )
                generated_paths.append(path)
                
            except Exception as e:
                logger.error(f"Failed to generate video {i+1}: {e}")
        
        logger.info(f"Generated {len(generated_paths)} character videos")
        return generated_paths
    
    def cleanup(self):
        """Clean up GPU memory."""
        if self.pipeline is not None:
            del self.pipeline
            self.pipeline = None
            
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            logger.info("Cleaned up video generator")


# Global video generator instance
video_generator = VideoGenerator()
