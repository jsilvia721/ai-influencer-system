"""Image generation using Stable Diffusion with LoRA support."""
import torch
from diffusers import StableDiffusionPipeline, DPMSolverMultistepScheduler
from diffusers.loaders import LoraLoaderMixin
from PIL import Image
from typing import Optional, List, Union
from pathlib import Path
import uuid
from loguru import logger

from ..utils.config import config
from ..utils.storage import storage


class ImageGenerator:
    """Generates images using Stable Diffusion with LoRA support."""
    
    def __init__(self):
        """Initialize the image generator."""
        self.pipeline = None
        self.current_lora = None
        self.device = config.get("models.stable_diffusion.device", "cpu")
        self.model_id = config.get("models.stable_diffusion.model_id", "runwayml/stable-diffusion-v1-5")
        
        # Ensure storage directories exist
        storage.ensure_local_dirs()
    
    def load_pipeline(self):
        """Load the Stable Diffusion pipeline."""
        if self.pipeline is not None:
            logger.info("Pipeline already loaded")
            return
        
        logger.info(f"Loading Stable Diffusion pipeline: {self.model_id}")
        
        # Load pipeline
        self.pipeline = StableDiffusionPipeline.from_pretrained(
            self.model_id,
            torch_dtype=torch.float16 if self.device != "cpu" else torch.float32,
            safety_checker=None,
            requires_safety_checker=False,
        )
        
        # Use DPM solver for faster inference
        self.pipeline.scheduler = DPMSolverMultistepScheduler.from_config(
            self.pipeline.scheduler.config
        )
        
        # Move to device
        self.pipeline = self.pipeline.to(self.device)
        
        # Enable memory efficient attention if using CUDA
        if self.device == "cuda":
            self.pipeline.enable_memory_efficient_attention()
            self.pipeline.enable_model_cpu_offload()
        
        logger.info(f"Pipeline loaded on device: {self.device}")
    
    def load_lora(self, lora_name: str, lora_scale: float = 1.0):
        """Load a LoRA model.
        
        Args:
            lora_name: Name of the LoRA file
            lora_scale: Scale/strength of the LoRA effect (0.0 to 1.0)
        """
        if self.pipeline is None:
            self.load_pipeline()
        
        # Find LoRA file
        lora_path = storage.load_lora(lora_name)
        if lora_path is None:
            raise FileNotFoundError(f"LoRA not found: {lora_name}")
        
        try:
            # Unload current LoRA if any
            if self.current_lora:
                self.pipeline.unload_lora_weights()
            
            # Load new LoRA
            self.pipeline.load_lora_weights(lora_path)
            self.current_lora = lora_name
            
            logger.info(f"Loaded LoRA: {lora_name} with scale {lora_scale}")
            
        except Exception as e:
            logger.error(f"Failed to load LoRA {lora_name}: {e}")
            raise
    
    def generate_image(
        self,
        prompt: str,
        negative_prompt: str = "blurry, low quality, distorted, deformed",
        lora_name: Optional[str] = None,
        lora_scale: float = 1.0,
        width: Optional[int] = None,
        height: Optional[int] = None,
        num_inference_steps: Optional[int] = None,
        guidance_scale: Optional[float] = None,
        seed: Optional[int] = None,
        save_image: bool = True,
        filename: Optional[str] = None
    ) -> Union[Image.Image, str]:
        """Generate an image from a text prompt.
        
        Args:
            prompt: Text prompt for image generation
            negative_prompt: Negative prompt to avoid certain features
            lora_name: Name of LoRA to use (optional)
            lora_scale: LoRA strength (0.0 to 1.0)
            width: Image width (defaults to config)
            height: Image height (defaults to config)
            num_inference_steps: Number of denoising steps (defaults to config)
            guidance_scale: Classifier-free guidance scale (defaults to config)
            seed: Random seed for reproducible generation
            save_image: Whether to save the image to storage
            filename: Custom filename (auto-generated if None)
            
        Returns:
            PIL Image or path to saved image if save_image=True
        """
        if self.pipeline is None:
            self.load_pipeline()
        
        # Load LoRA if specified
        if lora_name and lora_name != self.current_lora:
            self.load_lora(lora_name, lora_scale)
        
        # Use config defaults if not specified
        width = width or config.get("image_generation.width", 768)
        height = height or config.get("image_generation.height", 768)
        num_inference_steps = num_inference_steps or config.get("image_generation.num_inference_steps", 20)
        guidance_scale = guidance_scale or config.get("image_generation.guidance_scale", 7.5)
        
        # Set seed if provided
        if seed is not None:
            torch.manual_seed(seed)
            if torch.cuda.is_available():
                torch.cuda.manual_seed(seed)
        
        logger.info(f"Generating image with prompt: '{prompt[:50]}...'")
        logger.info(f"Parameters: {width}x{height}, steps={num_inference_steps}, guidance={guidance_scale}")
        
        try:
            # Generate image
            with torch.autocast(self.device if self.device != "cpu" else "cpu"):
                result = self.pipeline(
                    prompt=prompt,
                    negative_prompt=negative_prompt,
                    width=width,
                    height=height,
                    num_inference_steps=num_inference_steps,
                    guidance_scale=guidance_scale,
                    cross_attention_kwargs={"scale": lora_scale} if lora_name else None
                )
            
            image = result.images[0]
            
            if save_image:
                # Generate filename if not provided
                if filename is None:
                    filename = f"generated_{uuid.uuid4().hex[:8]}.png"
                elif not filename.endswith(('.png', '.jpg', '.jpeg')):
                    filename += '.png'
                
                # Save image
                saved_path = storage.save_image(image, filename)
                logger.info(f"Generated and saved image: {saved_path}")
                return saved_path
            else:
                logger.info("Generated image (not saved)")
                return image
                
        except Exception as e:
            logger.error(f"Failed to generate image: {e}")
            raise
    
    def generate_character_images(
        self,
        base_prompt: str,
        variations: List[str],
        lora_name: str,
        num_images: int = 1,
        **kwargs
    ) -> List[str]:
        """Generate multiple character images with variations.
        
        Args:
            base_prompt: Base prompt (should include trigger word)
            variations: List of variation prompts to append
            lora_name: LoRA model to use
            num_images: Number of images per variation
            **kwargs: Additional arguments for generate_image
            
        Returns:
            List of paths to saved images
        """
        generated_paths = []
        
        for i, variation in enumerate(variations):
            full_prompt = f"{base_prompt}, {variation}"
            
            for j in range(num_images):
                filename = f"character_var_{i+1}_{j+1}_{uuid.uuid4().hex[:6]}.png"
                
                try:
                    path = self.generate_image(
                        prompt=full_prompt,
                        lora_name=lora_name,
                        filename=filename,
                        **kwargs
                    )
                    generated_paths.append(path)
                    
                except Exception as e:
                    logger.error(f"Failed to generate variation {i+1}, image {j+1}: {e}")
        
        logger.info(f"Generated {len(generated_paths)} character images")
        return generated_paths
    
    def cleanup(self):
        """Clean up GPU memory."""
        if self.pipeline is not None:
            del self.pipeline
            self.pipeline = None
            self.current_lora = None
            
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            logger.info("Cleaned up image generator")


# Global image generator instance
image_generator = ImageGenerator()
