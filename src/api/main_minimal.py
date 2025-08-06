"""Minimal FastAPI interface for testing Docker setup."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
from loguru import logger
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from src.utils.config import config
    from src.utils.storage import storage
    HAS_FULL_SYSTEM = True
except ImportError as e:
    logger.warning(f"Full system not available: {e}")
    HAS_FULL_SYSTEM = False
    # Create minimal config for testing
    class MinimalConfig:
        def get(self, key, default=None):
            defaults = {
                "api.host": "0.0.0.0",
                "api.port": 8000,
                "logging.level": "INFO",
                "lora.trigger_word": "sks woman"
            }
            return defaults.get(key, default)
    config = MinimalConfig()

# Initialize FastAPI app
app = FastAPI(
    title="AI Influencer System (Minimal)",
    description="Minimal version for Docker testing",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Basic request models
class TestRequest(BaseModel):
    message: str

# API Routes
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "AI Influencer System API (Minimal Mode)",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "running",
        "mode": "minimal",
        "full_system_available": HAS_FULL_SYSTEM
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy", 
        "message": "System is operational",
        "full_system_available": HAS_FULL_SYSTEM
    }

@app.get("/config")
async def get_config():
    """Get current system configuration."""
    return {
        "trigger_word": config.get("lora.trigger_word"),
        "api_host": config.get("api.host"),
        "api_port": config.get("api.port"),
        "full_system_available": HAS_FULL_SYSTEM
    }

if HAS_FULL_SYSTEM:
    @app.get("/loras")
    async def list_loras():
        """List available LoRA models."""
        try:
            loras = storage.list_loras()
            return {"loras": loras, "count": len(loras)}
        except Exception as e:
            logger.error(f"Failed to list LoRAs: {e}")
            raise HTTPException(status_code=500, detail=str(e))
else:
    @app.get("/loras")
    async def list_loras():
        """Mock LoRA listing for minimal mode."""
        return {
            "loras": [],
            "count": 0,
            "message": "Full system not available - this is minimal mode"
        }

@app.post("/test")
async def test_endpoint(request: TestRequest):
    """Test endpoint for Docker verification."""
    return {
        "success": True,
        "message": f"Received: {request.message}",
        "timestamp": "2024-01-01T00:00:00Z",
        "full_system_available": HAS_FULL_SYSTEM
    }

if __name__ == "__main__":
    # Configure logging
    logger.remove()
    logger.add(sys.stdout, level=config.get("logging.level", "INFO"))
    
    # Run the API server
    uvicorn.run(
        "src.api.main_minimal:app",
        host=config.get("api.host", "0.0.0.0"),
        port=config.get("api.port", 8000),
        reload=False,
        log_level=config.get("logging.level", "info").lower()
    )
