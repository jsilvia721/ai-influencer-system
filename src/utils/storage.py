"""Storage utilities for local and cloud storage."""
import os
import boto3
from pathlib import Path
from typing import Optional, Union
from PIL import Image
import torch
from loguru import logger

from .config import config


class StorageManager:
    """Manages local and S3 storage operations."""
    
    def __init__(self):
        """Initialize storage manager."""
        self.local_base_path = Path(config.get("storage.local.base_path", "./data/"))
        self.use_s3 = bool(config.get("storage.aws.bucket_name"))
        
        if self.use_s3:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=config.get("storage.aws.access_key_id"),
                aws_secret_access_key=config.get("storage.aws.secret_access_key"),
                region_name=config.get("storage.aws.region", "us-east-1")
            )
            self.bucket_name = config.get("storage.aws.bucket_name")
        else:
            self.s3_client = None
            self.bucket_name = None
    
    def ensure_local_dirs(self):
        """Ensure all local directories exist."""
        dirs = [
            self.local_base_path,
            self.local_base_path / "images",
            self.local_base_path / "video_clips",
            self.local_base_path / "loras",
            self.local_base_path / "final_videos"
        ]
        
        for dir_path in dirs:
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured directory exists: {dir_path}")
    
    def save_image(self, image: Union[Image.Image, torch.Tensor], filename: str, 
                   subdir: str = "images") -> str:
        """Save image locally and optionally to S3.
        
        Args:
            image: PIL Image or torch tensor
            filename: Filename to save as
            subdir: Subdirectory within data folder
            
        Returns:
            Local path where image was saved
        """
        # Ensure local directory exists
        local_dir = self.local_base_path / subdir
        local_dir.mkdir(parents=True, exist_ok=True)
        
        local_path = local_dir / filename
        
        # Convert tensor to PIL if necessary
        if isinstance(image, torch.Tensor):
            # Assume tensor is in [0, 1] range and needs to be converted to [0, 255]
            image = (image * 255).clamp(0, 255).byte()
            if len(image.shape) == 4:  # Batch dimension
                image = image[0]
            if image.shape[0] == 3:  # CHW to HWC
                image = image.permute(1, 2, 0)
            image = Image.fromarray(image.cpu().numpy())
        
        # Save locally
        image.save(local_path)
        logger.info(f"Saved image to {local_path}")
        
        # Upload to S3 if configured
        if self.use_s3:
            try:
                s3_key = f"{subdir}/{filename}"
                self.s3_client.upload_file(str(local_path), self.bucket_name, s3_key)
                logger.info(f"Uploaded image to S3: s3://{self.bucket_name}/{s3_key}")
            except Exception as e:
                logger.error(f"Failed to upload image to S3: {e}")
        
        return str(local_path)
    
    def save_video(self, video_path: Union[str, Path], filename: str, 
                   subdir: str = "video_clips") -> str:
        """Save video locally and optionally to S3.
        
        Args:
            video_path: Path to existing video file
            filename: Filename to save as
            subdir: Subdirectory within data folder
            
        Returns:
            Local path where video was saved
        """
        # Ensure local directory exists
        local_dir = self.local_base_path / subdir
        local_dir.mkdir(parents=True, exist_ok=True)
        
        local_path = local_dir / filename
        
        # Copy/move video file
        import shutil
        shutil.copy2(video_path, local_path)
        logger.info(f"Saved video to {local_path}")
        
        # Upload to S3 if configured
        if self.use_s3:
            try:
                s3_key = f"{subdir}/{filename}"
                self.s3_client.upload_file(str(local_path), self.bucket_name, s3_key)
                logger.info(f"Uploaded video to S3: s3://{self.bucket_name}/{s3_key}")
            except Exception as e:
                logger.error(f"Failed to upload video to S3: {e}")
        
        return str(local_path)
    
    def load_lora(self, lora_name: str) -> Optional[str]:
        """Load LoRA model path.
        
        Args:
            lora_name: Name of the LoRA file (with or without .safetensors extension)
            
        Returns:
            Path to LoRA file if found, None otherwise
        """
        if not lora_name.endswith('.safetensors'):
            lora_name += '.safetensors'
        
        local_path = self.local_base_path / "loras" / lora_name
        
        if local_path.exists():
            logger.info(f"Found LoRA at {local_path}")
            return str(local_path)
        
        # Try to download from S3 if configured
        if self.use_s3:
            try:
                s3_key = f"loras/{lora_name}"
                self.s3_client.download_file(self.bucket_name, s3_key, str(local_path))
                logger.info(f"Downloaded LoRA from S3: {s3_key}")
                return str(local_path)
            except Exception as e:
                logger.error(f"Failed to download LoRA from S3: {e}")
        
        logger.warning(f"LoRA not found: {lora_name}")
        return None
    
    def list_loras(self) -> list[str]:
        """List available LoRA models.
        
        Returns:
            List of LoRA filenames
        """
        loras = []
        local_lora_dir = self.local_base_path / "loras"
        
        if local_lora_dir.exists():
            loras.extend([f.name for f in local_lora_dir.glob("*.safetensors")])
        
        return sorted(list(set(loras)))


# Global storage manager instance
storage = StorageManager()
