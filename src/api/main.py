"""FastAPI web interface for the AI influencer system."""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
from loguru import logger

from ..orchestration.pipeline import content_pipeline
from ..image_generation.generator import image_generator
from ..video_generation.generator import video_generator
from ..utils.config import config
from ..utils.storage import storage

# Initialize FastAPI app
app = FastAPI(
    title="AI Influencer System",
    description="Generate consistent AI influencer content using LoRA models",
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

# Serve static files
app.mount("/static", StaticFiles(directory="data"), name="static")


# Pydantic models for API requests
class ImageGenerationRequest(BaseModel):
    prompt: str
    lora_name: Optional[str] = None
    negative_prompt: str = "blurry, low quality, distorted, deformed"
    width: Optional[int] = None
    height: Optional[int] = None
    num_inference_steps: Optional[int] = None
    guidance_scale: Optional[float] = None
    seed: Optional[int] = None


class VideoGenerationRequest(BaseModel):
    prompt: str
    lora_name: Optional[str] = None
    image_generation_params: Optional[Dict[str, Any]] = None
    video_generation_params: Optional[Dict[str, Any]] = None


class ContentCreationRequest(BaseModel):
    concept: str
    lora_name: str
    num_videos: int = 3
    content_type: str = "social_media_post"


class BatchContentRequest(BaseModel):
    concepts: List[str]
    lora_name: str
    videos_per_concept: int = 2


class ShowcaseRequest(BaseModel):
    lora_name: str
    showcase_type: str = "personality"


# API Routes
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "AI Influencer System API",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "message": "System is operational"}


@app.get("/loras")
async def list_loras():
    """List available LoRA models."""
    try:
        loras = storage.list_loras()
        return {"loras": loras, "count": len(loras)}
    except Exception as e:
        logger.error(f"Failed to list LoRAs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/config")
async def get_config():
    """Get current system configuration."""
    return {
        "trigger_word": config.get("lora.trigger_word"),
        "device": config.get("models.stable_diffusion.device"),
        "image_size": {
            "width": config.get("image_generation.width"),
            "height": config.get("image_generation.height")
        },
        "video_size": {
            "width": config.get("video_generation.width"),
            "height": config.get("video_generation.height"),
            "fps": config.get("video_generation.fps")
        }
    }


@app.post("/generate/image")
async def generate_image(request: ImageGenerationRequest):
    """Generate a single image."""
    try:
        logger.info(f"Generating image: {request.prompt[:50]}...")
        
        image_path = image_generator.generate_image(
            prompt=request.prompt,
            negative_prompt=request.negative_prompt,
            lora_name=request.lora_name,
            width=request.width,
            height=request.height,
            num_inference_steps=request.num_inference_steps,
            guidance_scale=request.guidance_scale,
            seed=request.seed,
            save_image=True
        )
        
        return {
            "success": True,
            "image_path": image_path,
            "message": "Image generated successfully"
        }
        
    except Exception as e:
        logger.error(f"Image generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate/video")
async def generate_video(request: VideoGenerationRequest):
    """Generate a single video from prompt."""
    try:
        logger.info(f"Generating video: {request.prompt[:50]}...")
        
        video_path = video_generator.generate_video_from_prompt_and_image(
            prompt=request.prompt,
            image_generator=image_generator,
            lora_name=request.lora_name,
            image_generation_kwargs=request.image_generation_params or {},
            video_generation_kwargs=request.video_generation_params or {}
        )
        
        return {
            "success": True,
            "video_path": video_path,
            "message": "Video generated successfully"
        }
        
    except Exception as e:
        logger.error(f"Video generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/create/content")
async def create_content(request: ContentCreationRequest, background_tasks: BackgroundTasks):
    """Create content from a concept."""
    try:
        logger.info(f"Creating content for concept: {request.concept}")
        
        # Run content creation in background if it takes too long
        result = content_pipeline.create_content_from_concept(
            concept=request.concept,
            lora_name=request.lora_name,
            num_videos=request.num_videos,
            content_type=request.content_type
        )
        
        return {
            "success": result["success"],
            "result": result,
            "message": "Content creation completed" if result["success"] else "Content creation failed"
        }
        
    except Exception as e:
        logger.error(f"Content creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/create/batch")
async def create_batch_content(request: BatchContentRequest):
    """Create content for multiple concepts in batch."""
    try:
        logger.info(f"Creating batch content for {len(request.concepts)} concepts")
        
        results = content_pipeline.generate_batch_content(
            concepts=request.concepts,
            lora_name=request.lora_name,
            videos_per_concept=request.videos_per_concept
        )
        
        successful = sum(1 for r in results if r.get("success", False))
        
        return {
            "success": successful > 0,
            "results": results,
            "summary": {
                "total": len(request.concepts),
                "successful": successful,
                "failed": len(request.concepts) - successful
            },
            "message": f"Batch processing completed: {successful}/{len(request.concepts)} successful"
        }
        
    except Exception as e:
        logger.error(f"Batch content creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/create/showcase")
async def create_showcase(request: ShowcaseRequest):
    """Create a character showcase video."""
    try:
        logger.info(f"Creating {request.showcase_type} showcase")
        
        result = content_pipeline.create_character_showcase(
            lora_name=request.lora_name,
            showcase_type=request.showcase_type
        )
        
        return {
            "success": result["success"],
            "result": result,
            "message": f"{request.showcase_type.title()} showcase created successfully" if result["success"] else "Showcase creation failed"
        }
        
    except Exception as e:
        logger.error(f"Showcase creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/cleanup")
async def cleanup_resources():
    """Clean up GPU memory and resources."""
    try:
        content_pipeline.cleanup()
        return {"success": True, "message": "Resources cleaned up successfully"}
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Background task routes for long-running operations
@app.post("/create/content/async")
async def create_content_async(request: ContentCreationRequest, background_tasks: BackgroundTasks):
    """Create content asynchronously."""
    task_id = f"content_{request.concept}_{hash(request.lora_name) % 10000}"
    
    def run_content_creation():
        try:
            result = content_pipeline.create_content_from_concept(
                concept=request.concept,
                lora_name=request.lora_name,
                num_videos=request.num_videos,
                content_type=request.content_type
            )
            logger.info(f"Async content creation completed: {task_id}")
            # In a real implementation, you'd store this result in a database or cache
        except Exception as e:
            logger.error(f"Async content creation failed: {task_id}, {e}")
    
    background_tasks.add_task(run_content_creation)
    
    return {
        "success": True,
        "task_id": task_id,
        "message": "Content creation started in background",
        "status": "processing"
    }


if __name__ == "__main__":
    # Configure logging
    logger.add("logs/api.log", rotation="100 MB", level=config.get("logging.level", "INFO"))
    
    # Run the API server
    uvicorn.run(
        "src.api.main:app",
        host=config.get("api.host", "0.0.0.0"),
        port=config.get("api.port", 8000),
        reload=True,
        log_level=config.get("logging.level", "info").lower()
    )
