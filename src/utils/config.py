"""Configuration management utilities."""
import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from loguru import logger

# Load environment variables
load_dotenv()


class Config:
    """Configuration manager for the AI influencer system."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration.
        
        Args:
            config_path: Path to config file. Defaults to config/config.yaml
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"
        
        self.config_path = Path(config_path)
        self._config = self._load_config()
        self._apply_env_overrides()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            logger.info(f"Loaded configuration from {self.config_path}")
            return config
        except Exception as e:
            logger.error(f"Failed to load config from {self.config_path}: {e}")
            raise
    
    def _apply_env_overrides(self):
        """Apply environment variable overrides."""
        # Device override
        if device := os.getenv("DEVICE"):
            self._config["models"]["stable_diffusion"]["device"] = device
            self._config["models"]["stable_video_diffusion"]["device"] = device
        
        # AWS overrides
        if aws_key := os.getenv("AWS_ACCESS_KEY_ID"):
            self._config["storage"]["aws"]["access_key_id"] = aws_key
        
        if aws_secret := os.getenv("AWS_SECRET_ACCESS_KEY"):
            self._config["storage"]["aws"]["secret_access_key"] = aws_secret
        
        if bucket := os.getenv("S3_BUCKET_NAME"):
            self._config["storage"]["aws"]["bucket_name"] = bucket
        
        # API overrides
        if host := os.getenv("API_HOST"):
            self._config["api"]["host"] = host
        
        if port := os.getenv("API_PORT"):
            self._config["api"]["port"] = int(port)
        
        # Logging override
        if log_level := os.getenv("LOG_LEVEL"):
            self._config["logging"]["level"] = log_level
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation.
        
        Args:
            key: Configuration key (e.g., 'models.stable_diffusion.device')
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        keys = key.split('.')
        value = self._config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any):
        """Set configuration value using dot notation.
        
        Args:
            key: Configuration key (e.g., 'models.stable_diffusion.device')
            value: Value to set
        """
        keys = key.split('.')
        config = self._config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    @property
    def raw(self) -> Dict[str, Any]:
        """Get raw configuration dictionary."""
        return self._config


# Global config instance
config = Config()
